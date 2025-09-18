const socket = io();  // minden oldal betöltéskor csatlakozik

socket.on('connect', () => {
    console.log('Connected to Socket.IO');
    socket.emit('join', { room: 'user_{{ current_user.user_id }}' });
});

// Értesítés és chatablak
socket.on('new_offer', function(data) {
    showNotification(data);
});

function showNotification(data) {
    const $notif = $(`
        <div class="offer-notification">
            Új ajánlat: <b>${data.price} ${data.currency}</b>
            <a href="#" class="open-chat" data-cargo="${data.cargo_id}" data-offer="${data.offer_id}">Chat megnyitása</a>
        </div>
    `);
    $('body').append($notif);
    setTimeout(() => { $notif.fadeOut(400, () => $notif.remove()); }, 5000);

    $notif.find('.open-chat').on('click', function(e) {
        e.preventDefault();
        openChatWindow(data.cargo_id, data.offer_id, data.from_user);
        $notif.remove();
    });
}

function openChatWindow(cargoId, offerId, fromUser) {
    if ($('#chat-' + cargoId + '-' + offerId).length) return; // már nyitva
    const $chat = $(`
        <div class="chat-window" id="chat-${cargoId}-${offerId}">
            <div class="chat-header">
                Chat ${fromUser} <span class="close-chat">&times;</span>
            </div>
            <div class="chat-messages"></div>
            <div class="chat-input">
                <input type="text" placeholder="Üzenet..." />
                <button>Send</button>
            </div>
        </div>
    `);
    $('body').append($chat);

    // bezárás
    $chat.find('.close-chat').on('click', function() { $chat.remove(); });

    // üzenetküldés
    $chat.find('button').on('click', function() {
        const msg = $chat.find('input').val();
        if (msg.trim() === '') return;
        socket.emit('send_message', {
            cargo_id: cargoId,
            offer_id: offerId,
            message: msg
        });
        $chat.find('.chat-messages').append(`<div class="msg own">${msg}</div>`);
        $chat.find('input').val('');
    });
}

// Üzenetek fogadása
socket.on('receive_message', function(data) {
    const $chat = $('#chat-' + data.cargo_id + '-' + data.offer_id);
    if ($chat.length) {
        $chat.find('.chat-messages').append(`<div class="msg">${data.message}</div>`);
    } else {
        // ha nincs nyitva, lehet értesítést dobni
        showNotification({
            cargo_id: data.cargo_id,
            offer_id: data.offer_id,
            price: '',
            currency: '',
            from_user: data.from_user
        });
    }
});
