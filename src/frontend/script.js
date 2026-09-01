async function enviar() {
    const input = document.getElementById('userInput');
    const chat = document.getElementById('chat');
    const pergunta = input.value;
    
    if (!pergunta) return;

    chat.innerHTML += `<p><b>Você:</b> ${pergunta}</p>`;
    input.value = '';

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                session_id: "user123", 
                pergunta: pergunta 
            })
        });

        if (!response.ok) {
            throw new Error('Erro ao comunicar com o servidor');
        }

        const data = await response.json();
        chat.innerHTML += `<p><b>EficientIA:</b> ${data.resposta}</p>`;
        chat.scrollTop = chat.scrollHeight;
    } catch (error) {
        chat.innerHTML += `<p style="color: red;"><b>Erro:</b> ${error.message}</p>`;
    }
}

// Permitir envio com a tecla "Enter"
document.getElementById('userInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        enviar();
    }
});
