from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import logging
from ...models import Ticket, UserProfile
from ...extensions import db, notifier_manager
import html
from ...decorators import admin_required

logger = logging.getLogger(__name__)
tickets_api_bp = Blueprint('tickets_api', __name__)

@tickets_api_bp.route('/report', methods=['POST'])
@login_required
def report_issue():
    """Utilizador comum reporta um erro."""
    try:
        data = request.get_json()
        media_title = html.escape(str(data.get('media_title', '')).strip())
        issue_type = html.escape(str(data.get('issue_type', '')).strip())
        description = html.escape(str(data.get('description', '')).strip())

        if not issue_type:
            return jsonify({"success": False, "message": "O tipo de problema é obrigatório."}), 400

        ticket = Ticket(
            user_plex_id=current_user.id,
            username=current_user.username,
            media_title=media_title,
            issue_type=issue_type,
            description=description,
            status='open'
        )
        db.session.add(ticket)
        db.session.commit()

        # Notificar os administradores
        msg = (
            f"⚠️ *Novo Problema Reportado*\n"
            f"Utilizador: {current_user.username}\n"
            f"Mídia: {media_title}\n"
            f"Problema: {issue_type}\n"
            f"Descrição: {description}"
        )
        notifier_manager.send_admin_notification(msg)

        return jsonify({"success": True, "message": "O seu reporte foi enviado com sucesso. Iremos analisar em breve!"})
    except Exception as e:
        logger.error(f"Erro ao reportar ticket: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Falha ao enviar reporte."}), 500

@tickets_api_bp.route('/', methods=['GET'])
@login_required
@admin_required
def list_tickets():
    """Admin lista tickets."""
    try:
        status_filter = request.args.get('status', 'open')
        query = Ticket.query
        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
            
        tickets = query.order_by(Ticket.created_at.desc()).all()
        
        result = []
        for t in tickets:
            result.append({
                "id": t.id,
                "username": t.username,
                "media_title": t.media_title,
                "issue_type": t.issue_type,
                "description": t.description,
                "status": t.status,
                "created_at": t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else None,
                "resolved_at": t.resolved_at.strftime('%Y-%m-%d %H:%M') if t.resolved_at else None,
                "admin_notes": t.admin_notes
            })
            
        return jsonify({"success": True, "tickets": result})
    except Exception as e:
        logger.error(f"Erro ao listar tickets: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erro ao carregar tickets."}), 500

@tickets_api_bp.route('/<int:ticket_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_ticket(ticket_id):
    """Admin resolve um ticket."""
    try:
        data = request.get_json()
        admin_notes = html.escape(str(data.get('admin_notes', '')).strip())
        
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return jsonify({"success": False, "message": "Ticket não encontrado."}), 404
            
        ticket.status = 'resolved'
        ticket.admin_notes = admin_notes
        from datetime import datetime
        ticket.resolved_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({"success": True, "message": "Ticket marcado como resolvido."})
    except Exception as e:
        logger.error(f"Erro ao resolver ticket {ticket_id}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erro ao atualizar ticket."}), 500
