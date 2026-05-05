import os
import json
import logging
import zipfile
from datetime import datetime, timedelta
import glob

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import CONFIG_DIR

logger = logging.getLogger(__name__)

class BackupService:
    def __init__(self, config_provider):
        """
        config_provider é uma função que retorna um dicionário com as configurações
        (ex: lambda: load_or_create_config())
        """
        self.config_provider = config_provider
        self.backup_dir = os.path.join(CONFIG_DIR, 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def _get_files_to_backup(self):
        # Backup config.json and .db files (incluindo wal e shm para sqlite em WAL)
        files = []
        for root, _, filenames in os.walk(CONFIG_DIR):
            if 'backups' in root or 'cache' in root:
                continue # Ignorar pastas de backups e cache
            for filename in filenames:
                if filename.endswith('.json') or filename.endswith('.db') or filename.endswith('.db-wal') or filename.endswith('.db-shm') or filename.endswith('.pem'):
                    files.append(os.path.join(root, filename))
        return files

    def run_backup(self):
        config = self.config_provider()
        if not config.get('BACKUP_ENABLED', False):
            logger.info("Backup automático está desativado.")
            return False

        logger.info("A iniciar rotina de backup...")
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_painel_plex_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            # Criar arquivo ZIP localmente
            files_to_backup = self._get_files_to_backup()
            if not files_to_backup:
                logger.warning("Nenhum ficheiro para incluir no backup.")
                return False

            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_backup:
                    if os.path.isfile(file):
                        # Caminho relativo para manter estrutura se houver pastas internas (ex: certs)
                        arcname = os.path.relpath(file, start=CONFIG_DIR)
                        zipf.write(file, arcname)
                        
            logger.info(f"Backup local criado com sucesso: {backup_path}")

            # Limpeza de backups locais antigos
            retention_days = config.get('BACKUP_LOCAL_RETENTION_DAYS', 7)
            self._cleanup_local_backups(retention_days)

            # Upload Google Drive
            if config.get('BACKUP_GDRIVE_ENABLED', False):
                self._upload_to_gdrive(backup_path, backup_filename, config)
                
            return True

        except Exception as e:
            logger.error(f"Erro ao executar a rotina de backup: {e}", exc_info=True)
            return False

    def _cleanup_local_backups(self, retention_days):
        if retention_days <= 0:
            return
            
        cutoff = datetime.now() - timedelta(days=retention_days)
        backup_files = glob.glob(os.path.join(self.backup_dir, 'backup_painel_plex_*.zip'))
        count = 0
        for f in backup_files:
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(f))
                if mtime < cutoff:
                    os.remove(f)
                    count += 1
            except Exception as e:
                logger.warning(f"Não foi possível remover backup antigo {f}: {e}")
                
        if count > 0:
            logger.info(f"{count} backups locais antigos removidos (retenção: {retention_days} dias).")

    def _upload_to_gdrive(self, filepath, filename, config):
        credentials_json = config.get('BACKUP_GDRIVE_CREDENTIALS', '')
        folder_id = str(config.get('BACKUP_GDRIVE_FOLDER_ID', '')).strip()

        if not credentials_json or not folder_id:
            logger.error("Credenciais ou ID da pasta do Google Drive não configurados.")
            return False

        try:
            # Parse credenciais do JSON fornecido
            creds_dict = json.loads(credentials_json)
            scopes = ['https://www.googleapis.com/auth/drive']
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
            service = build('drive', 'v3', credentials=creds, cache_discovery=False)

            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            media = MediaFileUpload(filepath, mimetype='application/zip', resumable=True)

            logger.info(f"A iniciar upload para o Google Drive (Folder ID: {folder_id})...")
            file = service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
            logger.info(f"Upload para o Google Drive concluído. ID do ficheiro: {file.get('id')}")
            
            # Limpar backups antigos no Google Drive
            self._cleanup_gdrive_backups(service, folder_id, config.get('BACKUP_LOCAL_RETENTION_DAYS', 7))

            return True
        except json.JSONDecodeError:
            logger.error("As credenciais do Google Drive fornecidas não são um JSON válido.")
            return False
        except Exception as e:
            logger.error(f"Erro no upload para o Google Drive: {e}", exc_info=True)
            return False

    def _cleanup_gdrive_backups(self, service, folder_id, retention_days):
        if retention_days <= 0:
            return
        
        try:
            query = f"'{folder_id}' in parents and name contains 'backup_painel_plex_' and trashed=false"
            results = service.files().list(q=query, spaces='drive', fields='nextPageToken, files(id, name, createdTime)', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            items = results.get('files', [])

            cutoff = datetime.utcnow() - timedelta(days=retention_days)
            count = 0
            for item in items:
                created_time_str = item.get('createdTime')
                if created_time_str:
                    created_time_str = created_time_str.replace('Z', '')
                    if '.' in created_time_str:
                        created_time_str = created_time_str.split('.')[0]
                    
                    created_time = datetime.strptime(created_time_str, '%Y-%m-%dT%H:%M:%S')
                    if created_time < cutoff:
                        service.files().delete(fileId=item.get('id')).execute()
                        count += 1
                        
            if count > 0:
                logger.info(f"{count} backups antigos removidos do Google Drive (retenção: {retention_days} dias).")
        except Exception as e:
            logger.warning(f"Erro ao limpar backups antigos no Google Drive: {e}")
