// chat.js - SINGLE SOURCE OF TRUTH for chat and socket

// Socket inicializálás
window.socket = window.socket || io();
const socket = window.socket;

// ---- Globális chat ablak kezelés ----
const chatWindows = [];

// Chat ablak nyitása
function openChatWindow(cargoId, offerId, fromUser, profilePictureUrl, offerData, userCompany, fromUserId, toUserId) {
    if ($('#chat-' + cargoId + '-' + offerId).length) return;

    if (chatWindows.length >= 3) {
        const $oldestChat = chatWindows.shift();
        $oldestChat.remove();
    }

    let partnerCompany = offerData.partner_company || '';
    const $chat = $(`
        <div class="chat-window" id="chat-${cargoId}-${offerId}" style="position: fixed; bottom: 10px; width: 300px; border: 1px solid #ccc; border-radius: 10px; background-color: #fff; z-index: 1000;">
            <div class="chat-header" style="cursor:pointer; display:flex; align-items:center; justify-content:space-between;">
                <div class="chat-header-left" style="display:flex; align-items:center;">
                    <img src="${profilePictureUrl || '/static/uploads/profile_pictures/user.png'}" 
                         alt="${fromUser}" 
                         style="width:30px; height:30px; border-radius:50%; object-fit:cover; margin-right:8px;">
                    <span class="chat-username">${fromUser} <small>(${userCompany || partnerCompany})</small></span>
                </div>
                <button class="close-chat" title="Kilépés">×</button>
            </div>
            <div class="chat-body">
                <div class="chat-messages" style="height:300px; overflow-y:auto; margin-top:5px;"></div>
                <div class="chat-input" style="margin-top:5px;">
                    <input type="text" placeholder="Üzenet..." class="chat-field" />
                    <button class="send-msg">Send</button>
                </div>
            </div>
        </div>
    `);

    $chat.data("from-user-id", fromUserId);
    $chat.data("to-user-id", toUserId);

    $('body').append($chat);
    chatWindows.push($chat);
    chatWindows.forEach(($win, index) => $win.css('right', 10 + index * 310 + 'px'));

    // Join the room
    const roomName = `chat_${cargoId}_${offerId}`;
    socket.emit('join', { room: roomName });

    const $messages = $chat.find('.chat-messages');

    // Load chat history
    $.getJSON(`/chat_history/${cargoId}/${offerId}`, function(resp) {
        if (resp && Array.isArray(resp.messages)) {
            resp.messages.forEach(function(m) {
                const isOwn = (typeof CURRENT_USER_ID !== 'undefined' && m.from_user_id === CURRENT_USER_ID);
                // console.log(m.from_user_id)
                $messages.append(`
                    <div class="msg ${isOwn ? 'own' : ''}" style="${isOwn ? 'text-align:right; background:#e6f7ff;' : 'text-align:left; background:#f0f0f0;'} padding:4px 8px; border-radius:5px; margin-bottom:3px;">
                        ${m.message}
                    </div>
                `);
            });
            $messages.scrollTop($messages[0].scrollHeight);
        }
    });

    if (offerData) {
        // Én vagyok az ajánlattevő vagy a cargo tulajdonosa
        const isOwn = (offerData.from_user_id === CURRENT_USER_ID);

        // console.log(offerData.from_user_id)
        // Partner mindig a másik fél
        let partnerName = isOwn ? offerData.to_user : offerData.from_user;
        let partnerProfilePic = offerData.profile_picture || '/static/uploads/profile_pictures/default.png';
        // Ha a backend nem küld cégnevet, azt itt nem tudjuk, marad üres

        console.log(offerData.partner_company)

        // Gombok: csak a cargo tulajdonos látja
        let buttonsLeft = "";
        let buttonsRight = "";
        if (!isOwn && offerData.cargo_owner_id === CURRENT_USER_ID) {
            buttonsLeft = `<button id="accept-offer">✅ Elfogad</button>`;
            buttonsRight = `<button id="decline-offer">❌ Elutasít</button>`;
        }

        $messages.append(`
            <div class="msg offer-summary" style="background:#f0f0f0; padding:5px; border-radius:5px; margin-bottom:5px; display:flex; justify-content:space-between; position: sticky; top: 0">
                <div class="offer-left" style="display:flex; flex-direction:column; align-items:flex-start;">
                    <span>⬆️${offerData.origin}</span>
                    <small><b>${offerData.pickup_date}</b></small>
                    <b style="color: red">${offerData.price} ${offerData.currency.toUpperCase()}</b>
                    ${buttonsLeft}
                </div>
                <div class="offer-right" style="display:flex; flex-direction:column; align-items:flex-end;">
                    <span>${offerData.destination}⬇️</span>
                    <small><b>${offerData.arrival_date}</b></small>
                    <div style="height: 24px;"></div>
                    ${buttonsRight}
                </div>
            </div>
            ${offerData.note ? `
            <div style="display:flex; align-items:center; margin-top:5px;">
                <img src="${partnerProfilePic}" alt="${partnerName}" style="width:30px; height:30px; border-radius:50%; object-fit:cover; margin-right:8px;">
                <span>${offerData.note}</span>
            </div>` : ''}
        `);
    }

    const $header = $chat.find('.chat-header');
    const $body = $chat.find('.chat-body');
    const $username = $chat.find('.chat-username');
    const $img = $chat.find('img');

    $header.on('click', function(e) {
        if (!$(e.target).hasClass('close-chat')) {
            if ($body.is(':visible')) {
                $body.slideUp(150);
                $img.css({width:'20px', height:'20px', marginRight:'5px'});
                $username.css({fontSize:'0.8em'});
            } else {
                $body.slideDown(150);
                $img.css({width:'30px', height:'30px', marginRight:'8px'});
                $username.css({fontSize:'1em'});
            }
        }
    });

    $chat.find('.close-chat').on('click', function() {
        const index = chatWindows.indexOf($chat);
        if (index > -1) chatWindows.splice(index, 1);
        $chat.remove();
        chatWindows.forEach(($win, idx) => $win.css('right', 10 + idx * 310 + 'px'));
    });

    $chat.find('button.send-msg').on('click', sendMessage);
    $chat.find('.chat-input input').on('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); sendMessage(); }
    });

    function sendMessage() {
        const $input = $chat.find('.chat-input input');
        const msg = $input.val();
        if (msg.trim() === '') return;

        const senderId = $chat.data('from-user-id');
        const recipientId = $chat.data('to-user-id');

        socket.emit('send_message', {
            cargo_id: cargoId,
            offer_id: offerId,
            message: msg,
            from_user_id: senderId,
            to_user_id: recipientId
        });

        $chat.find('.chat-messages').append(`
            <div class="msg own" style="text-align:right; background:#e6f7ff; padding:4px 8px; border-radius:5px; margin-bottom:3px;">${msg}</div>
        `);
        $chat.find('.chat-messages').scrollTop($chat.find('.chat-messages')[0].scrollHeight);

        $input.val('');
        $input.focus();
    }
}

// Üzenetfogadás
socket.on('receive_message', function(data) {
    // Avoid duplicating our own messages (we already appended them locally)
    if (typeof CURRENT_USER_ID !== 'undefined' && data.from_user_id === CURRENT_USER_ID) {
        return;
    }
    const $chat = $('#chat-' + data.cargo_id + '-' + data.offer_id);
    if ($chat.length) {
        $chat.find('.chat-messages').append(`
            <div class="msg" style="text-align:left; background:#f0f0f0; padding:4px 8px; border-radius:5px; margin-bottom:3px;">
                ${data.message}
            </div>
        `);
        $chat.find('.chat-messages').scrollTop($chat.find('.chat-messages')[0].scrollHeight);
    } else {
        showNotification(data);
    }
});

// Ajánlat értesítés
function showNotification(data) {
    const $notif = $(`
        <div class="offer-notification">
            <a href="#" class="open-chat" data-cargo="${data.cargo_id}" data-offer="${data.offer_id}">
                <div><b>${data.from_user}</b> új ajánlatot tett:</div>
                <div>${data.origin} → ${data.destination}</div>
                <div><b>${data.price} ${data.currency.toUpperCase()}</b></div>
            </a>
        </div>
    `);
    $('body').append($notif);
    setTimeout(() => $notif.fadeOut(1000, () => $notif.remove()), 10000);

    $notif.find('.open-chat').on('click', function(e) {
        e.preventDefault();

        // --- IDE JÖN AZ OTHER_USER_ID SZÁMÍTÁS ---
        const OTHER_USER_ID = (data.from_user_id === CURRENT_USER_ID)
            ? data.to_user_id
            : data.from_user_id;

        openChatWindow(
            data.cargo_id,
            data.offer_id,
            data.from_user,
            data.profile_picture,
            data,
            data.user_company,
            CURRENT_USER_ID,  // a jelenlegi felhasználó ID-ja
            OTHER_USER_ID     // a chat partner ID-ja
        );
        $notif.remove();
    });
}

socket.on('new_offer', function(data) { showNotification(data); });
