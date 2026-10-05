const CHAT_API_BASE =
    "http://127.0.0.1:5000/api/chat";

let currentConversationId = null;
let currentChatUser = null;

let chatPollingInterval = null;
let typingStopTimeout = null;

let allChatUsers = [];
let allConversations = [];

let currentUserId = null;

let chatInitialized = false;


/* =========================================================
   GET CHAT TOKEN
========================================================= */

function getChatToken() {

    return localStorage.getItem("token");

}


/* =========================================================
   CHAT API REQUEST
========================================================= */

async function chatApiRequest(url, options = {}) {

    const token = getChatToken();

    if (!token) {

        throw new Error(
            "You are not logged in."
        );

    }

    const headers = {

        "Content-Type": "application/json",

        "Authorization": `Bearer ${token}`,

        ...(options.headers || {})

    };

    const response = await fetch(
        url,
        {
            ...options,
            headers
        }
    );

    let data = {};

    try {

        data = await response.json();

    } catch (error) {

        data = {};

    }

    if (!response.ok) {

        throw new Error(
            data.message ||
            data.error ||
            "Something went wrong."
        );

    }

    return data;

}


/* =========================================================
   LOAD CURRENT LOGGED-IN USER
========================================================= */

async function loadCurrentChatUser() {

    const token = getChatToken();

    if (!token) {

        console.error(
            "No authentication token found."
        );

        return false;

    }

    try {

        const response = await fetch(

            "http://127.0.0.1:5000/api/auth/me",

            {
                method: "GET",

                headers: {

                    "Authorization":
                        `Bearer ${token}`,

                    "Content-Type":
                        "application/json"

                }

            }

        );

        if (!response.ok) {

            console.error(
                "Unable to get current user:",
                response.status
            );

            return false;

        }

        const data =
            await response.json();

        console.log(
            "Current logged-in user:",
            data
        );

        /*
         * /auth/me may return:
         *
         * {
         *     id: 2,
         *     email: "...",
         *     role: "employee"
         * }
         *
         * OR:
         *
         * {
         *     user: {
         *         id: 2,
         *         ...
         *     }
         * }
         */

        const user =
            data.user || data;

        if (
            user &&
            user.id !== undefined &&
            user.id !== null
        ) {

            currentUserId =
                Number(user.id);

            console.log(
                "Current user ID:",
                currentUserId
            );

            return true;

        }

        console.error(
            "Current user ID was not found in /auth/me response."
        );

        return false;

    } catch (error) {

        console.error(
            "Error loading current user:",
            error
        );

        return false;

    }

}


/* =========================================================
   INITIALIZE CHAT
========================================================= */

async function initializeChat() {

    /*
     * Prevent duplicate event listeners
     * and duplicate polling.
     */

    if (chatInitialized) {

        await loadCurrentChatUser();

        await loadChatUsers();

        await loadConversations();

        if (currentConversationId) {

            await loadMessages(
                currentConversationId,
                true
            );

            await checkTypingStatus();

        }

        return;

    }

    chatInitialized = true;


    /* -----------------------------------------
       Load logged-in user first
    ----------------------------------------- */

    const userLoaded =
        await loadCurrentChatUser();

    if (!userLoaded) {

        console.error(
            "Chat cannot determine the logged-in user."
        );

        return;

    }


    /* -----------------------------------------
       Setup UI
    ----------------------------------------- */

    setupChatSearch();

    setupChatMessageInput();


    /* -----------------------------------------
       Load chat data
    ----------------------------------------- */

    await loadChatUsers();

    await loadConversations();


    /* -----------------------------------------
       Start polling
    ----------------------------------------- */

    startChatPolling();

}


/* =========================================================
   LOAD CHAT USERS
========================================================= */

async function loadChatUsers() {

    try {

        const users =
            await chatApiRequest(
                `${CHAT_API_BASE}/users`
            );

        allChatUsers = users;

        populateNewChatUsers();

    } catch (error) {

        console.error(
            "Error loading chat users:",
            error
        );

    }

}


/* =========================================================
   POPULATE NEW CHAT USERS
========================================================= */

function populateNewChatUsers() {

    const select =
        document.getElementById(
            "new-chat-user"
        );

    if (!select) {

        return;

    }

    select.innerHTML = `

        <option value="">
            Select User
        </option>

    `;


    allChatUsers.forEach(user => {

        /*
         * Do not show the currently logged-in
         * user in the new chat list.
         */

        if (
            Number(user.id) ===
            Number(currentUserId)
        ) {

            return;

        }

        const option =
            document.createElement(
                "option"
            );

        option.value =
            user.id;

        option.textContent =
            `${user.name || user.email} (${capitalize(user.role)})`;

        select.appendChild(option);

    });

}


/* =========================================================
   LOAD CONVERSATIONS
========================================================= */

async function loadConversations() {

    try {

        const conversations =
            await chatApiRequest(
                `${CHAT_API_BASE}/conversations`
            );

        allConversations =
            conversations;

        renderConversations();

    } catch (error) {

        console.error(
            "Error loading conversations:",
            error
        );

    }

}


/* =========================================================
   RENDER CONVERSATIONS
========================================================= */

function renderConversations() {

    const container =
        document.getElementById(
            "chat-conversations-list"
        );

    if (!container) {

        return;

    }

    container.innerHTML = "";


    if (!allConversations.length) {

        container.innerHTML = `

            <div class="chat-empty">

                <i class="fa-regular fa-comments"></i>

                <p>
                    No conversations yet.
                </p>

                <small>
                    Start a new chat to begin messaging.
                </small>

            </div>

        `;

        return;

    }


    allConversations.forEach(
        conversation => {

            if (!conversation.user) {

                return;

            }

            const user =
                conversation.user;


            const item =
                document.createElement(
                    "div"
                );

            item.className =
                "chat-conversation-item";


            if (
                Number(
                    conversation.conversation_id
                ) ===
                Number(
                    currentConversationId
                )
            ) {

                item.classList.add(
                    "active"
                );

            }


            const avatarLetter =
                getInitial(
                    user.name ||
                    user.email
                );


            const preview =
                conversation.last_message ||
                "No messages yet";


            const time =
                conversation.last_message_time

                    ? formatMessageTime(
                        conversation.last_message_time
                    )

                    : "";


            let unreadBadge = "";


            if (
                Number(
                    conversation.unread_count
                ) > 0
            ) {

                unreadBadge = `

                    <span class="chat-unread-badge">

                        ${conversation.unread_count}

                    </span>

                `;

            }


            item.innerHTML = `

                <div
                    class="chat-conversation-avatar avatar"
                >

                    ${escapeHtml(
                        avatarLetter
                    )}

                </div>


                <div
                    class="chat-conversation-content"
                >

                    <div
                        class="chat-conversation-top"
                    >

                        <strong>

                            ${escapeHtml(
                                user.name || user.email
                            )}

                        </strong>


                        <span
                            class="chat-conversation-time"
                        >

                            ${escapeHtml(
                                time
                            )}

                        </span>

                    </div>


                    <div
                        class="chat-conversation-bottom"
                    >

                        <span
                            class="chat-conversation-preview"
                        >

                            ${escapeHtml(
                                preview
                            )}

                        </span>


                        ${unreadBadge}

                    </div>

                </div>

            `;


            item.addEventListener(
                "click",
                () => {

                    openConversation(
                        conversation.conversation_id,
                        user
                    );

                }
            );


            container.appendChild(
                item
            );

        }
    );

}


/* =========================================================
   OPEN CONVERSATION
========================================================= */

async function openConversation(
    conversationId,
    user
) {

    currentConversationId =
        conversationId;

    currentChatUser =
        user;


    updateChatHeader(
        user
    );


    enableChatInput();


    /*
     * Load messages first.
     */

    await loadMessages(
        conversationId,
        false
    );


    /*
     * Mark messages from the other user
     * as read.
     */

    await markMessagesAsRead(
        conversationId
    );


    /*
     * Refresh conversation list so
     * unread count disappears.
     */

    await loadConversations();


    /*
     * Check typing status.
     */

    await checkTypingStatus();

}


/* =========================================================
   UPDATE CHAT HEADER
========================================================= */

function updateChatHeader(user) {

    const nameElement =
        document.getElementById(
            "chat-header-name"
        );

    const roleElement =
        document.getElementById(
            "chat-header-role"
        );

    const avatarElement =
        document.getElementById(
            "chat-header-avatar"
        );

    const typingElement =
        document.getElementById(
            "chat-header-typing"
        );


    if (nameElement) {

        nameElement.textContent =
            user.name ||
            user.email ||
            "User";

    }


    if (roleElement) {

        roleElement.textContent =
            capitalize(
                user.role
            );

    }


    if (avatarElement) {

        avatarElement.textContent =
            getInitial(
                user.name ||
                user.email
            );

    }


    if (typingElement) {

        typingElement.classList.add(
            "hidden-view"
        );

    }

}


/* =========================================================
   LOAD MESSAGES
========================================================= */

async function loadMessages(
    conversationId,
    preserveScroll = false
) {

    try {

        const messages =
            await chatApiRequest(

                `${CHAT_API_BASE}/conversations/${conversationId}/messages`

            );


        /*
         * Backend returns messages
         * directly as an array.
         */

        renderMessages(
            messages,
            preserveScroll
        );


    } catch (error) {

        console.error(
            "Error loading messages:",
            error
        );

    }

}


/* =========================================================
   RENDER MESSAGES
========================================================= */

function renderMessages(
    messages,
    preserveScroll = false
) {

    const container =
        document.getElementById(
            "chat-messages"
        );


    if (!container) {

        return;

    }


    /*
     * Save scroll position.
     */

    const wasNearBottom =
        container.scrollHeight -
        container.scrollTop -
        container.clientHeight < 100;


    container.innerHTML = "";


    /*
     * Make sure response is an array.
     */

    if (!Array.isArray(messages)) {

        console.error(
            "Messages response is not an array:",
            messages
        );

        container.innerHTML = `

            <div class="chat-welcome">

                <div class="chat-welcome-icon">

                    <i class="fa-regular fa-comments"></i>

                </div>

                <h3>
                    Unable to load messages
                </h3>

                <p>
                    The server returned an unexpected response.
                </p>

            </div>

        `;

        return;

    }


    /*
     * No messages.
     */

    if (!messages.length) {

        container.innerHTML = `

            <div class="chat-welcome">

                <div class="chat-welcome-icon">

                    <i class="fa-regular fa-comments"></i>

                </div>

                <h3>
                    No messages yet
                </h3>

                <p>
                    Send a message to start the conversation.
                </p>

            </div>

        `;

        return;

    }


    /*
     * Render every message.
     */

    messages.forEach(
        message => {

            /*
             * Compare sender ID with
             * logged-in user's ID.
             */

            const isSent =
                Number(
                    message.sender_id
                ) ===
                Number(
                    currentUserId
                );


            const wrapper =
                document.createElement(
                    "div"
                );


            /*
             * Own message = right.
             * Other message = left.
             */

            wrapper.className =
                isSent
                    ? "chat-message sent"
                    : "chat-message received";


            const bubble =
                document.createElement(
                    "div"
                );

            bubble.className =
                "chat-message-bubble";


            const text =
                document.createElement(
                    "p"
                );

            text.className =
                "chat-message-text";

            text.textContent =
                message.message || "";


            const footer =
                document.createElement(
                    "div"
                );

            footer.className =
                "chat-message-footer";


            const time =
                document.createElement(
                    "span"
                );

            time.className =
                "chat-message-time";

            time.textContent =
                formatMessageTime(
                    message.created_at
                );


            footer.appendChild(
                time
            );


            /* =================================================
               SENT / SEEN STATUS
            ================================================= */

            if (isSent) {

                const status =
                    document.createElement(
                        "span"
                    );

                status.className =
                    "chat-message-status";


                if (
                    message.is_read === true
                ) {

                    status.textContent =
                        "Seen";

                    status.classList.add(
                        "seen"
                    );

                } else {

                    status.textContent =
                        "Sent";

                }


                footer.appendChild(
                    status
                );

            }


            bubble.appendChild(
                text
            );

            bubble.appendChild(
                footer
            );

            wrapper.appendChild(
                bubble
            );

            container.appendChild(
                wrapper
            );

        }
    );


    /*
     * Scroll to bottom when:
     *
     * - opening conversation
     * - sending message
     * - already near bottom
     */

    if (
        !preserveScroll ||
        wasNearBottom
    ) {

        container.scrollTop =
            container.scrollHeight;

    }

}


/* =========================================================
   SEND CHAT MESSAGE
========================================================= */

async function sendChatMessage() {

    if (!currentConversationId) {

        return;

    }


    const input =
        document.getElementById(
            "chat-message-input"
        );


    if (!input) {

        return;

    }


    const message =
        input.value.trim();


    if (!message) {

        return;

    }


    try {

        /*
         * Stop typing indicator.
         */

        clearTimeout(
            typingStopTimeout
        );

        await sendTypingStatus(
            false
        );


        /*
         * Send message.
         */

        await chatApiRequest(

            `${CHAT_API_BASE}/conversations/${currentConversationId}/messages`,

            {

                method: "POST",

                body: JSON.stringify({

                    message: message

                })

            }

        );


        /*
         * Clear input.
         */

        input.value = "";

        autoResizeChatInput();


        /*
         * Reload messages.
         */

        await loadMessages(
            currentConversationId,
            false
        );


        /*
         * Refresh conversation preview.
         */

        await loadConversations();


        /*
         * Keep input focused.
         */

        input.focus();


    } catch (error) {

        console.error(
            "Error sending message:",
            error
        );

        alert(
            error.message ||
            "Unable to send message."
        );

    }

}


/* =========================================================
   MARK MESSAGES AS READ
========================================================= */

async function markMessagesAsRead(
    conversationId
) {

    try {

        await chatApiRequest(

            `${CHAT_API_BASE}/conversations/${conversationId}/read`,

            {

                method: "PATCH"

            }

        );

    } catch (error) {

        console.error(
            "Error marking messages as read:",
            error
        );

    }

}


/* =========================================================
   SEND TYPING STATUS
========================================================= */

async function sendTypingStatus(
    isTyping
) {

    if (!currentConversationId) {

        return;

    }


    try {

        await chatApiRequest(

            `${CHAT_API_BASE}/conversations/${currentConversationId}/typing`,

            {

                method: "POST",

                body: JSON.stringify({

                    is_typing: isTyping

                })

            }

        );

    } catch (error) {

        console.error(
            "Error updating typing status:",
            error
        );

    }

}


/* =========================================================
   CHECK OTHER USER TYPING STATUS
========================================================= */

async function checkTypingStatus() {

    if (!currentConversationId) {

        return;

    }


    try {

        const data =
            await chatApiRequest(

                `${CHAT_API_BASE}/conversations/${currentConversationId}/typing`

            );


        const typingElement =
            document.getElementById(
                "chat-header-typing"
            );


        if (!typingElement) {

            return;

        }


        if (
            data.is_typing === true
        ) {

            typingElement.classList.remove(
                "hidden-view"
            );

        } else {

            typingElement.classList.add(
                "hidden-view"
            );

        }


    } catch (error) {

        console.error(
            "Error checking typing status:",
            error
        );

    }

}


/* =========================================================
   HANDLE CHAT TYPING
========================================================= */

function handleChatTyping() {

    if (!currentConversationId) {

        return;

    }


    sendTypingStatus(
        true
    );


    clearTimeout(
        typingStopTimeout
    );


    typingStopTimeout =
        setTimeout(

            () => {

                sendTypingStatus(
                    false
                );

            },

            2000

        );

}


/* =========================================================
   NEW CHAT
========================================================= */

function openNewChat() {

    populateNewChatUsers();


    const select =
        document.getElementById(
            "new-chat-user"
        );


    if (select) {

        select.value = "";

    }


    toggleModal(
        "modal-new-chat",
        true
    );

}


/* =========================================================
   START NEW CHAT
========================================================= */

async function startNewChat() {

    const select =
        document.getElementById(
            "new-chat-user"
        );


    if (!select) {

        return;

    }


    const userId =
        select.value;


    if (!userId) {

        alert(
            "Please select a user."
        );

        return;

    }


    try {

        const response =
            await chatApiRequest(

                `${CHAT_API_BASE}/conversations`,

                {

                    method: "POST",

                    body: JSON.stringify({

                        user_id:
                            Number(userId)

                    })

                }

            );


        toggleModal(
            "modal-new-chat",
            false
        );


        await loadConversations();


        const conversation =
            allConversations.find(

                item =>

                    Number(
                        item.conversation_id
                    ) ===
                    Number(
                        response.conversation_id
                    )

            );


        if (conversation) {

            await openConversation(

                conversation.conversation_id,

                conversation.user

            );

        } else {

            const user =
                allChatUsers.find(

                    item =>

                        Number(item.id) ===
                        Number(userId)

                );


            if (user) {

                await openConversation(

                    response.conversation_id,

                    user

                );

            }

        }


    } catch (error) {

        console.error(
            "Error creating conversation:",
            error
        );


        alert(

            error.message ||
            "Unable to start conversation."

        );

    }

}


/* =========================================================
   CHAT SEARCH
========================================================= */

function setupChatSearch() {

    const searchInput =
        document.getElementById(
            "chat-user-search"
        );


    if (!searchInput) {

        return;

    }


    searchInput.addEventListener(

        "input",

        function () {

            const search =
                this.value
                    .trim()
                    .toLowerCase();


            const items =
                document.querySelectorAll(
                    ".chat-conversation-item"
                );


            items.forEach(
                item => {

                    const text =
                        item.textContent
                            .toLowerCase();


                    if (
                        text.includes(search)
                    ) {

                        item.style.display =
                            "";

                    } else {

                        item.style.display =
                            "none";

                    }

                }
            );

        }

    );

}


/* =========================================================
   CHAT MESSAGE INPUT
========================================================= */

function setupChatMessageInput() {

    const input =
        document.getElementById(
            "chat-message-input"
        );


    if (!input) {

        return;

    }


    input.addEventListener(

        "input",

        function () {

            autoResizeChatInput();


            if (
                this.value.trim()
            ) {

                handleChatTyping();

            } else {

                clearTimeout(
                    typingStopTimeout
                );

                sendTypingStatus(
                    false
                );

            }

        }

    );


    input.addEventListener(

        "keydown",

        function (event) {

            if (

                event.key === "Enter" &&

                !event.shiftKey

            ) {

                event.preventDefault();

                sendChatMessage();

            }

        }

    );

}


/* =========================================================
   AUTO RESIZE TEXTAREA
========================================================= */

function autoResizeChatInput() {

    const input =
        document.getElementById(
            "chat-message-input"
        );


    if (!input) {

        return;

    }


    input.style.height =
        "auto";


    input.style.height =
        `${input.scrollHeight}px`;

}


/* =========================================================
   ENABLE CHAT INPUT
========================================================= */

function enableChatInput() {

    const input =
        document.getElementById(
            "chat-message-input"
        );


    const button =
        document.getElementById(
            "send-chat-message-btn"
        );


    if (input) {

        input.disabled =
            false;

        input.focus();

    }


    if (button) {

        button.disabled =
            false;

    }

}


/* =========================================================
   DISABLE CHAT INPUT
========================================================= */

function disableChatInput() {

    const input =
        document.getElementById(
            "chat-message-input"
        );


    const button =
        document.getElementById(
            "send-chat-message-btn"
        );


    if (input) {

        input.disabled =
            true;

    }


    if (button) {

        button.disabled =
            true;

    }

}


/* =========================================================
   CHAT POLLING
========================================================= */

function startChatPolling() {

    /*
     * Prevent duplicate intervals.
     */

    if (chatPollingInterval) {

        clearInterval(
            chatPollingInterval
        );

    }


    chatPollingInterval =
        setInterval(

            async () => {

                try {

                    /*
                     * Refresh conversation list.
                     */

                    await loadConversations();


                    /*
                     * Refresh current messages.
                     */

                    if (
                        currentConversationId
                    ) {

                        await loadMessages(

                            currentConversationId,

                            true

                        );


                        /*
                         * Check typing status.
                         */

                        await checkTypingStatus();

                    }

                } catch (error) {

                    console.error(
                        "Chat polling error:",
                        error
                    );

                }

            },

            3000

        );

}


/* =========================================================
   GET INITIAL
========================================================= */

function getInitial(value) {

    if (!value) {

        return "?";

    }


    return value
        .trim()
        .charAt(0)
        .toUpperCase();

}


/* =========================================================
   CAPITALIZE
========================================================= */

function capitalize(value) {

    if (!value) {

        return "";

    }


    return value
        .charAt(0)
        .toUpperCase()
        +
        value.slice(1);

}


/* =========================================================
   FORMAT MESSAGE TIME
========================================================= */

function formatMessageTime(
    dateString
) {

    if (!dateString) {

        return "";

    }


    const date =
        new Date(
            dateString
        );


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return "";

    }


    return date.toLocaleTimeString(

        [],

        {

            hour: "numeric",

            minute: "2-digit"

        }

    );

}


/* =========================================================
   ESCAPE HTML
========================================================= */

function escapeHtml(value) {

    if (

        value === null ||

        value === undefined

    ) {

        return "";

    }


    const div =
        document.createElement(
            "div"
        );


    div.textContent =
        String(value);


    return div.innerHTML;

}


/* =========================================================
   INITIALIZE CHAT WHEN VISIBLE
========================================================= */

function initializeChatWhenVisible() {

    const chatView =
        document.getElementById(
            "view-chat"
        );


    if (!chatView) {

        return;

    }


    /*
     * Only initialize Chat when the
     * Chat panel is actually visible.
     *
     * IMPORTANT:
     *
     * We do NOT modify switchView().
     *
     * app.js remains responsible for
     * switching between Dashboard,
     * Employees, Departments, Leave,
     * Attendance, Payroll and Chat.
     */

    if (
        !chatView.classList.contains(
            "hidden-view"
        )
    ) {

        initializeChat();

    }

}


/* =========================================================
   DOM CONTENT LOADED
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        /*
         * Chat input starts disabled.
         */

        disableChatInput();


        /*
         * If Chat happens to be visible
         * when the page first loads,
         * initialize it.
         */

        initializeChatWhenVisible();


        /*
         * Watch ONLY the Chat panel's
         * class attribute.
         *
         * app.js changes the visibility.
         *
         * When Chat becomes visible,
         * initializeChat() runs.
         *
         * We never change the visibility
         * ourselves.
         */

        const chatView =
            document.getElementById(
                "view-chat"
            );


        if (!chatView) {

            return;

        }


        const chatViewObserver =
            new MutationObserver(
                function () {

                    initializeChatWhenVisible();

                }
            );


        chatViewObserver.observe(
            chatView,
            {
                attributes: true,
                attributeFilter: [
                    "class"
                ]
            }
        );

    }
);