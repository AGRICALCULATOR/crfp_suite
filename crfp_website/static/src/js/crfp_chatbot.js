/**
 * CR Farm Products — AI Chatbot Widget
 *
 * Floating chat button in the bottom-right corner of all CR Farm website pages.
 * Sends messages to /crfarm/chatbot/message (JSON-RPC) and displays responses.
 */
(function () {
    'use strict';

    // Only initialise on /crfarm/* pages
    if (!window.location.pathname.startsWith('/crfarm')) return;

    /* ── State ── */
    let isOpen = false;
    let isLoading = false;
    let conversationHistory = [];   // [{role, content}]

    /* ── Build DOM ── */
    const widget = document.createElement('div');
    widget.id = 'crfarm-chatbot';
    widget.innerHTML = `
        <button id="crfarm-chat-toggle" aria-label="Open chat assistant" title="Chat with our assistant">
            <span class="crfarm-chat-icon">💬</span>
            <span class="crfarm-chat-label">Chat</span>
        </button>

        <div id="crfarm-chat-window" role="dialog" aria-label="CR Farm assistant" hidden>
            <div id="crfarm-chat-header">
                <div class="crfarm-chat-avatar">🌱</div>
                <div>
                    <div class="crfarm-chat-title">CR Farm Assistant</div>
                    <div class="crfarm-chat-subtitle">Typically replies instantly</div>
                </div>
                <button id="crfarm-chat-close" aria-label="Close chat">&times;</button>
            </div>

            <div id="crfarm-chat-messages">
                <div class="crfarm-msg crfarm-msg-bot">
                    <p>Hi! 👋 I'm the CR Farm Products virtual assistant.</p>
                    <p>I can help you with questions about our products (cassava, eddoes, malanga…), packaging, export logistics, and more.</p>
                    <p>How can I help you today?</p>
                </div>
            </div>

            <div id="crfarm-chat-input-row">
                <input id="crfarm-chat-input" type="text"
                       placeholder="Type your message…"
                       autocomplete="off" maxlength="500"/>
                <button id="crfarm-chat-send" aria-label="Send message">&#10148;</button>
            </div>
            <div id="crfarm-chat-footer">
                Powered by Claude AI &nbsp;·&nbsp;
                <a href="/crfarm/contact" style="color:#a8e6b0;">Get a formal quote</a>
            </div>
        </div>
    `;
    document.body.appendChild(widget);

    /* ── Element refs ── */
    const toggleBtn = document.getElementById('crfarm-chat-toggle');
    const closeBtn  = document.getElementById('crfarm-chat-close');
    const chatWin   = document.getElementById('crfarm-chat-window');
    const messagesEl = document.getElementById('crfarm-chat-messages');
    const inputEl   = document.getElementById('crfarm-chat-input');
    const sendBtn   = document.getElementById('crfarm-chat-send');

    /* ── Toggle open/close ── */
    function openChat() {
        chatWin.hidden = false;
        isOpen = true;
        toggleBtn.setAttribute('aria-expanded', 'true');
        inputEl.focus();
    }

    function closeChat() {
        chatWin.hidden = true;
        isOpen = false;
        toggleBtn.setAttribute('aria-expanded', 'false');
    }

    toggleBtn.addEventListener('click', () => isOpen ? closeChat() : openChat());
    closeBtn.addEventListener('click', closeChat);

    /* ── Message rendering ── */
    function appendMessage(role, text) {
        const div = document.createElement('div');
        div.className = `crfarm-msg crfarm-msg-${role === 'user' ? 'user' : 'bot'}`;
        // Convert newlines to <br>
        div.innerHTML = `<p>${escapeHtml(text).replace(/\n/g, '<br/>')}</p>`;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function appendTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'crfarm-msg crfarm-msg-bot crfarm-typing';
        div.id = 'crfarm-typing';
        div.innerHTML = '<span></span><span></span><span></span>';
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return div;
    }

    function removeTypingIndicator() {
        const el = document.getElementById('crfarm-typing');
        if (el) el.remove();
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /* ── Send message to backend ── */
    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text || isLoading) return;

        inputEl.value = '';
        isLoading = true;
        sendBtn.disabled = true;

        appendMessage('user', text);
        conversationHistory.push({ role: 'user', content: text });

        const typing = appendTypingIndicator();

        try {
            const response = await fetch('/crfarm/chatbot/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    id: Date.now(),
                    params: {
                        message: text,
                        history: conversationHistory.slice(-20),   // last 10 turns
                    },
                }),
            });

            const json = await response.json();
            removeTypingIndicator();

            if (json.result && json.result.response) {
                const reply = json.result.response;
                appendMessage('assistant', reply);
                conversationHistory.push({ role: 'assistant', content: reply });
            } else {
                appendMessage('assistant',
                    'Sorry, I encountered an issue. Please try again or use the contact form.');
            }
        } catch (err) {
            removeTypingIndicator();
            appendMessage('assistant',
                'Connection error. Please check your internet connection and try again.');
        } finally {
            isLoading = false;
            sendBtn.disabled = false;
            inputEl.focus();
        }
    }

    /* ── Event listeners ── */
    sendBtn.addEventListener('click', sendMessage);
    inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-open on first visit to contact page (helpful nudge)
    if (window.location.pathname === '/crfarm/contact') {
        setTimeout(openChat, 2500);
    }

})();
