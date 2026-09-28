document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chat-form");
    const messagesContainer = document.getElementById("chat-messages");
    const sendButton = document.getElementById("send-button");
    const processingIndicator = document.getElementById("chat-processing");
    const errorContainer = document.getElementById("chat-error");

    if (!form || !messagesContainer || !sendButton) {
        return;
    }

    const messageInput = form.querySelector("[name='content']");

    if (!messageInput) {
        return;
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function formatMessageTime(isoTimestamp) {
        const date = new Date(isoTimestamp);

        return new Intl.DateTimeFormat("en-IN", {
            timeZone: "Asia/Kolkata",
            month: "short",
            day: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    }

    function createMessageElement({
        role,
        content,
        createdAt,
    }) {
        const row = document.createElement("div");

        row.className =
            "message-row " +
            (
                role === "user"
                    ? "message-row-user"
                    : "message-row-assistant"
            );

        const bubble = document.createElement("div");

        bubble.className =
            "message-bubble " +
            (
                role === "user"
                    ? "message-bubble-user"
                    : "message-bubble-assistant"
            );

        const time = document.createElement("div");
        time.className = "message-time";
        time.textContent = formatMessageTime(createdAt);

        const contentElement = document.createElement("div");
        contentElement.className = "message-content";
        contentElement.textContent = content;

        bubble.appendChild(time);
        bubble.appendChild(contentElement);
        row.appendChild(bubble);

        return row;
    }

    function appendMessage({
        role,
        content,
        createdAt,
    }) {
        const emptyChat =
            messagesContainer.querySelector(".empty-chat");

        if (emptyChat) {
            emptyChat.remove();
        }

        messagesContainer.appendChild(
            createMessageElement({
                role,
                content,
                createdAt,
            })
        );

        scrollToBottom();
    }

    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.classList.remove("d-none");
    }

    function clearError() {
        errorContainer.textContent = "";
        errorContainer.classList.add("d-none");
    }

    function setProcessing(processing) {
        sendButton.disabled = processing;
        messageInput.disabled = processing;

        if (processing) {
            processingIndicator.classList.remove("d-none");
            sendButton.textContent = "Thinking...";
            sendButton.setAttribute("aria-busy", "true");
        } else {
            processingIndicator.classList.add("d-none");
            sendButton.textContent = "Send";
            sendButton.removeAttribute("aria-busy");
        }
    }

    // Open the conversation at the newest message.
    scrollToBottom();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (sendButton.disabled) {
            return;
        }

        clearError();

        const content = messageInput.value.trim();

        if (!content) {
            messageInput.focus();
            return;
        }

        const formData = new FormData(form);
        formData.set("content", content);

        appendMessage({
            role: "user",
            content,
            createdAt: new Date().toISOString(),
        });

        messageInput.value = "";
        setProcessing(true);

        try {
            const response = await fetch(
                form.action,
                {
                    method: "POST",
                    body: formData,
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json",
                    },
                }
            );

            let data;

            try {
                data = await response.json();
            } catch {
                throw new Error(
                    "Seher returned an unexpected response."
                );
            }

            if (!response.ok || !data.success) {
                throw new Error(
                    data?.error ||
                    "Seher could not respond right now. Please try again."
                );
            }

            appendMessage({
                role: "assistant",
                content: data.assistant_message.content,
                createdAt: data.assistant_message.created_at,
            });

        } catch (error) {
            showError(
                error.message ||
                "Seher could not respond right now. Please try again."
            );
        } finally {
            setProcessing(false);
            messageInput.focus();
            scrollToBottom();
        }
    });
});