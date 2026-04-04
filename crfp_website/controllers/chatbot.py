"""
CR Farm Website — AI chatbot controller.

Route
-----
POST /crfarm/chatbot/message   (type='jsonrpc')

Receives the user's message and conversation history,
calls the Claude API, and returns the assistant's response.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_CHAT_MODEL = 'claude-haiku-4-5-20251001'
_ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'
_MAX_HISTORY = 10   # maximum previous turns to send to the API

_CHAT_SYSTEM = """Eres el asistente virtual de CR Farm Products (CR Farm), una empresa costarricense
exportadora de productos agrícolas tropicales. CR Farm exporta raíces tropicales
(yuca, ñame, malanga, taro, jengibre, ñampí), coco, caña de azúcar y vegetales
a compradores en Norteamérica, Europa y el Caribe.

Tu función: ayudar a compradores potenciales con consultas sobre productos,
disponibilidad, proceso de exportación, incoterms, empaques y logística.

Normas de respuesta:
- Sé profesional, amigable y conciso.
- Responde en el mismo idioma que el usuario (español o inglés).
- Si no sabes algo con certeza, sugiere al usuario llenar el formulario de contacto
  en /crfarm/contacto para hablar con un ejecutivo.
- No inventes precios ni fechas de embarque específicas; esos detalles los proveen los ejecutivos.
- Limita tus respuestas a 3-4 párrafos máximo.
"""


class CrfarmChatbot(http.Controller):

    @http.route('/crfarm/chatbot/message', type='jsonrpc', auth='public', website=True)
    def chatbot_message(self, message='', history=None, **kwargs):
        """
        Receive a chat message from the user, call Claude, return response.

        Params (JSON-RPC params):
            message  (str)  — latest user message
            history  (list) — list of {role, content} dicts (prior turns)

        Returns:
            {response: str, error: str|None}
        """
        if not message or not message.strip():
            return {'response': '', 'error': 'empty_message'}

        api_key = request.env['ir.config_parameter'].sudo().get_param(
            'crfp_website.anthropic_api_key', '')
        if not api_key:
            _logger.warning('crfp_website chatbot: anthropic_api_key not configured')
            return {
                'response': (
                    'Lo sentimos, el asistente no está disponible en este momento. '
                    'Por favor use el formulario de contacto.'
                ),
                'error': 'no_api_key',
            }

        messages = self._build_messages(history or [], message.strip())
        response_text = self._call_claude(api_key, messages)

        if response_text is None:
            return {
                'response': (
                    'Ocurrió un error al procesar su mensaje. '
                    'Por favor intente de nuevo o use el formulario de contacto.'
                ),
                'error': 'api_error',
            }

        return {'response': response_text, 'error': None}

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _build_messages(self, history, new_message):
        """Assemble the messages list for the API, capped to avoid huge payloads."""
        messages = []
        # Only keep last N turns from history to limit token usage
        recent = history[-(_MAX_HISTORY * 2):] if history else []
        for turn in recent:
            role = turn.get('role', '')
            content = turn.get('content', '')
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': str(content)[:2000]})
        messages.append({'role': 'user', 'content': new_message})
        return messages

    def _call_claude(self, api_key, messages):
        """Call Anthropic API. Returns text content or None on error."""
        try:
            import requests as req
        except ImportError:
            _logger.error('crfp_website chatbot: requests library not available')
            return None

        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }
        payload = {
            'model': _CHAT_MODEL,
            'max_tokens': 768,
            'system': _CHAT_SYSTEM,
            'messages': messages,
        }
        try:
            resp = req.post(_ANTHROPIC_API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data.get('content', [])
            if content and content[0].get('type') == 'text':
                return content[0]['text']
        except Exception:
            _logger.exception('crfp_website chatbot: API call failed')
        return None
