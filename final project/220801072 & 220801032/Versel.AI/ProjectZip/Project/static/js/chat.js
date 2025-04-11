document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatHistory = document.getElementById('chat-history');
    const sendButton = document.getElementById('send-button');

    // Function to add a message to the chat history
    function addMessage(message, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        if (isUser) {
            messageContent.textContent = message;
        } else {
            // For AI messages, create a container for streaming text
            const streamingContainer = document.createElement('div');
            streamingContainer.className = 'streaming-text';
            messageContent.appendChild(streamingContainer);
        }
        
        messageDiv.appendChild(messageContent);
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        return messageContent;
    }

    // Function to stream text letter by letter
    function streamText(text, container, speed = 50) {  // Increased speed for better visibility
        let index = 0;
        const interval = setInterval(() => {
            if (index < text.length) {
                // Handle markdown formatting
                if (text[index] === '`' && text[index + 1] === '`' && text[index + 2] === '`') {
                    // Start of code block
                    const codeBlock = document.createElement('pre');
                    codeBlock.className = 'code-block';
                    container.appendChild(codeBlock);
                    index += 3;
                } else if (text[index] === '\n') {
                    container.appendChild(document.createElement('br'));
                    index++;
                } else {
                    // Add typing effect with cursor
                    const span = document.createElement('span');
                    span.className = 'typing-effect';
                    span.textContent = text[index];
                    container.appendChild(span);
                    index++;
                }
                chatHistory.scrollTop = chatHistory.scrollHeight;
            } else {
                clearInterval(interval);
                // Remove cursor after typing is complete
                const cursor = container.querySelector('.typing-cursor');
                if (cursor) {
                    cursor.remove();
                }
            }
        }, speed);
    }

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (!message) return;
        
        // Disable input and button while processing
        chatInput.disabled = true;
        sendButton.disabled = true;
        
        // Add user message to chat
        addMessage(message, true);
        
        try {
            const response = await fetch('/ai', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: message })
            });
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Add AI message container
            const aiMessageContainer = addMessage('', false);
            const streamingContainer = aiMessageContainer.querySelector('.streaming-text');
            
            // Add typing cursor
            const cursor = document.createElement('span');
            cursor.className = 'typing-cursor';
            streamingContainer.appendChild(cursor);
            
            if (data.stream) {
                // Stream the response letter by letter
                streamText(data.response, streamingContainer);
            } else {
                // For error messages, display immediately
                streamingContainer.textContent = data.response;
            }
            
        } catch (error) {
            console.error('Error:', error);
            const errorMessage = addMessage('An error occurred. Please try again.', false);
            errorMessage.querySelector('.streaming-text').textContent = 'An error occurred. Please try again.';
        } finally {
            // Re-enable input and button
            chatInput.disabled = false;
            sendButton.disabled = false;
            chatInput.value = '';
            chatInput.focus();
        }
    });
}); 