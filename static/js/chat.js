// chat.js - SINGLE SOURCE OF TRUTH for chat and socket

// Socket inicializálás
window.socket = window.socket || io();
const socket = window.socket;

socket.on('connect', () => {
    console.log("[DEBUG] Socket connected, id:", socket.id);
    if(typeof CURRENT_USER_ID !== 'undefined'){
        console.log("[DEBUG] Joining user room with CURRENT_USER_ID:", CURRENT_USER_ID);
        socket.emit("join_user", { user_id: CURRENT_USER_ID });
    } else {
        console.warn("[WARN] CURRENT_USER_ID nincs definiálva!");
    }
});

socket.on('disconnect', () => {
    console.log("[DEBUG] Socket disconnected");
});

// 🔔 Saját Socket.IO szoba csatlakozás (a backendben: join_user)
socket.emit("join_user");

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
    $.getJSON(`chat/chat_history/${cargoId}/${offerId}`, function(resp) {
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
        const isOwn = (offerData.from_user_id === CURRENT_USER_ID);
        console.log("isOwn:", isOwn, "from_user_id:", offerData.from_user_id, "CURRENT_USER_ID:", CURRENT_USER_ID);

        let partnerName = isOwn ? offerData.to_user : offerData.from_user;
        let partnerProfilePic = offerData.profile_picture || '/static/uploads/profile_pictures/default.png';

        // offerData.status lehet: "pending", "accepted", "declined"
        let priceColor = "#007bff"; // alap: pending → kék

        if(offerData.status === "accepted" || offerData.status === "finalized") {
            priceColor = "green";
        } else if(offerData.status === "declined" || offerData.status === "withdrawn") {
            priceColor = "red";
        }

        let buttonsHtml = "";
        if (!isOwn && offerData.cargo_owner_id === CURRENT_USER_ID) {
            if (offerData.status === "pending") {
                buttonsHtml = `
                    <div class="offer-buttons two-btns">
                        <button class="accept-offer-btn" data-offer-id="${offerData.offer_id}">✅ Elfogad</button>
                        <button class="decline-offer-btn" data-offer-id="${offerData.offer_id}">❌ Elutasít</button>
                    </div>`;
            }
        } else if (offerData.cargo_owner_id !== CURRENT_USER_ID) {
            // ajánlattevő saját oldala → új ajánlat
            if (offerData.status === "accepted") {
                buttonsHtml = `
                    <div class="offer-buttons one-btn">
                        <button class="finalize-offer-btn" data-offer-id="${offerData.offer_id}">✔ Véglegesít</button>
                        <button class="withdraw-offer-btn" data-offer-id="${offerData.offer_id}">↩ Visszavon</button>
                    </div>`;
            } else if (offerData.status === "pending" || offerData.status === "declined") {
                buttonsHtml = `
                    <div class="offer-buttons one-btn">
                        <button class="quick-offer-btn" data-offer-id="${offerData.offer_id}">🤝 Új ajánlat</button>
                    </div>`;
            }
        }


        $messages.append(`
        <div class="msg offer-summary" data-offer-id="${offerData.offer_id}" data-price="${offerData.price}" data-currency="${offerData.currency}" style="background:#f0f0f0; padding:5px; border-radius:5px; margin-bottom:5px; display:flex; justify-content:space-between; position: sticky; top: 0; flex-wrap: wrap">
            <div class="offer-left" style="display:flex; flex-direction:column; align-items:flex-start;">
                <span>⬆️${offerData.origin}</span>
                <small><b>${offerData.pickup_date}</b></small>
                <b class="offer-price" style="color: ${priceColor}">${offerData.price} ${offerData.currency.toUpperCase()}</b>
            </div>
            <div class="offer-right" style="display:flex; flex-direction:column; align-items:flex-end;">
                <span>${offerData.destination}⬇️</span>
                <small><b>${offerData.arrival_date}</b></small>
                <div style="height: 24px;"></div>
            </div>
            ${buttonsHtml}
            <!-- Ide tesszük a státusz divet -->
            <div class="offer-status" style="margin-top:5px;"></div>
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

// ===== Single Source of Truth: Offer Status Update (szöveg nélkül) =====
function updateOfferStatus(offerId, status) {
    let color = "#007bff"; // default: pending (kék)
    let statusText = "";   // mit írjon ki a badge
    let showButtons = true; // csak finalized/withdrawn esetén false

    if (status === 'accepted') {
        color = "green";
    } else if (status === 'declined') {
        color = "red";
    } else if (status === 'finalized') {
        color = "green"; // sötétzöld
        showButtons = false;
    } else if (status === 'withdrawn') {
        color = "red"; // sötétpiros
        showButtons = false;
    }

    // === 1️⃣ Lista elem frissítése (pl. /profile oldalon) ===
    const $offerItem = $(`#offer-${offerId}`);
    if ($offerItem.length) {
        $offerItem.removeClass('status-pending status-accepted status-declined status-finalized status-withdrawn')
                  .addClass(`status-${status}`);
        $offerItem.find('.offer-price').css("color", color);
        $offerItem.find('.offer-status').text(statusText).css("color", color);

        // Gombok eltüntetése, ha finalized/withdrawn
        if (!showButtons) {
            $offerItem.find('.offer-buttons').remove();
        }
    }

    // === 2️⃣ Chat ablakban frissítés ===
    const $chatOffer = $(`.offer-summary[data-offer-id="${offerId}"]`);
    if ($chatOffer.length) {
        $chatOffer.find('.offer-price').css("color", color);
        $chatOffer.find('.offer-status').text(statusText).css("color", color);

        // Ha finalized vagy withdrawn → gombok eltüntetése
        if (!showButtons) {
            $chatOffer.find('.offer-buttons').remove();
        }
    }

    // === 3️⃣ Toast értesítés, ha nincs sehol ===
    if (!$offerItem.length && !$chatOffer.length) {
        const msg = statusText || `Ajánlat státusz frissítve: ${status}`;
        showOfferToast(msg, status);
    }
}

// ===== Override AJAX accept/decline to use SST =====
$(document).on('click', '.accept-offer-btn', function() {
    const offerId = $(this).data('offer-id');
    if (!confirm("Biztosan elfogadod az ajánlatot?")) return;

    $.post(`cargo/offers/accept/${offerId}`, function(resp) {
        if (resp.success) {
            updateOfferStatus(offerId, 'accepted'); // szín és gomb frissítése
        }
    });
});

$(document).on('click', '.decline-offer-btn', function() {
    const offerId = $(this).data('offer-id');
    if (!confirm("Biztosan elutasítod az ajánlatot?")) return;

    $.post(`/cargo/offers/decline/${offerId}`, function(resp) {
        if (resp.success) {
            updateOfferStatus(offerId, 'declined'); // szín és gomb frissítése
        }
    });
});

// Véglegesítés
$(document).on('click', '.finalize-offer-btn', function() {
    const offerId = $(this).data('offer-id');
    $.post(`/cargo/offer/finalize_or_withdraw/${offerId}`, { action: 'finalize' }, function(resp) {
        if(resp.success){
            updateOfferStatus(offerId, 'finalized'); // gomb eltüntetése, szín változtatás
        } else {
            alert(resp.error);
        }
    });
});

// Visszavonás
$(document).on('click', '.withdraw-offer-btn', function() {
    const offerId = $(this).data('offer-id');
    $.post(`/cargo/offer/finalize_or_withdraw/${offerId}`, { action: 'withdraw' }, function(resp) {
        if(resp.success){
            updateOfferStatus(offerId, 'withdrawn'); // gomb eltüntetése, szín változtatás
        } else {
            alert(resp.error);
        }
    });
});

// ===== SocketIO override =====
socket.on('offer_status_update', function(data){
    updateOfferStatus(data.offer_id, data.status, data.origin, data.destination, data.price, data.currency);
});

// Gyors ajánlat modal
$(document).on('click', '.quick-offer-btn', function() {
    const offerId = $(this).data('offer-id');
    const $offerDiv = chatWindows.find($c => $c.find(`.offer-summary[data-offer-id="${offerId}"]`).length)
                     .find(`.offer-summary[data-offer-id="${offerId}"]`);
    if(!$offerDiv.length) return;

    const offerData = offerDataFromDOM($offerDiv);

    // Modal HTML (részlet, currency select)
    const currencies = ["EUR", "HUF"]; // itt bővítheted a támogatott pénznemeket
    const currencyOptions = currencies.map(c =>
        `<option value="${c}" ${c === offerData.currency ? "selected" : ""}>${c}</option>`
    ).join('');

    const $modal = $(`
        <div class="modal-overlay" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;justify-content:center;align-items:center;z-index:2000;">
            <div class="modal-content" style="background:#fff;padding:20px;border-radius:8px;width:300px;">
                <h3>Gyors ajánlat módosítása</h3>
                <label>Pickup date:<input type="date" class="modal-pickup" value="${offerData.pickup_date}"></label><br>
                <label>Arrival date:<input type="date" class="modal-arrival" value="${offerData.arrival_date}"></label><br>
                <label>Price:<input type="number" class="modal-price" value="${offerData.price}"></label><br>
                <label>Currency:
                    <select class="modal-currency">
                        ${currencyOptions}
                    </select>
                </label><br>
                <button class="modal-save-btn">Mentés</button>
                <br>
                <button class="modal-cancel-btn">Mégse</button>
            </div>
        </div>
    `);

    $('body').append($modal);

    $modal.find('.modal-cancel-btn').on('click', () => $modal.remove());

    $modal.find('.modal-save-btn').on('click', function() {
        const updatedData = {
            pickup_date: $modal.find('.modal-pickup').val(),
            arrival_date: $modal.find('.modal-arrival').val(),
            price: $modal.find('.modal-price').val(),
            currency: $modal.find('.modal-currency').val(),
        };

        $.ajax({
            url: `/cargo/offer/update/${offerId}`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(updatedData),
            success: function(resp) {
                if(resp.success) {
                    // 🔄 teljes oldal reload a profil oldalra
                    window.location.href = "/profile";
                } else {
                    alert("Hiba történt az ajánlat frissítésekor: " + resp.error);
                }
            },
            error: function(err) {
                console.error("[ERROR] Gyors ajánlat update sikertelen:", err);
                alert("Hiba történt az ajánlat frissítésekor!");
            }
        });
    });
});

// Segédfüggvény: DOM-ból offerData
function offerDataFromDOM($offerDiv) {
    return {
        origin: $offerDiv.find('.offer-left span').text().replace('⬆️',''),
        destination: $offerDiv.find('.offer-right span').text().replace('⬇️',''),
        pickup_date: $offerDiv.find('.offer-left small b').first().text(),
        arrival_date: $offerDiv.find('.offer-right small b').first().text(),
        price: $offerDiv.data('price'),       // backendből kapott price
        currency: $offerDiv.data('currency'), // backendből kapott currency
        note: $offerDiv.find('div[style*="align-items:center"]').text() || ''
    };
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

// Stackelt toast konténer
if($('#toast-container').length === 0){
    $('body').append('<div id="toast-container" style="position:fixed; top:10px; right:10px; z-index:3000; display:flex; flex-direction:column; gap:10px;"></div>');
}

// Segédfüggvény: stackelt toast értesítés
function showOfferToast(message, status) {
    console.log("[DEBUG] showOfferToast called:", message, status);
    const color = status === "accepted" ? "#28a745" : "#dc3545"; // zöld/piros

    if($('#toast-container').length === 0){
        console.log("[DEBUG] toast-container nem létezik, létrehozom");
        $('body').append('<div id="toast-container" style="position:fixed; top:10px; right:10px; z-index:3000; display:flex; flex-direction:column; gap:10px;"></div>');
    }

    const $toast = $(`
        <div style="
            background:${color};
            color:#fff;
            padding:10px 15px;
            border-radius:6px;
            min-width:200px;
            box-shadow:0 2px 8px rgba(0,0,0,0.2);
            opacity:0;
            transform: translateY(-20px);
            transition: all 0.4s ease;
        ">
            ${message}
        </div>
    `);

    $('#toast-container').prepend($toast);

    console.log("[DEBUG] Toast appended, animating in");
    setTimeout(() => $toast.css({opacity:1, transform:'translateY(0)'}), 10);

    setTimeout(() => {
        $toast.css({opacity:0, transform:'translateY(-20px)'});
        setTimeout(() => {
            $toast.remove();
            console.log("[DEBUG] Toast removed");
        }, 400);
    }, 4000);
}

// Frissített socket.on az ajánlat státuszhoz
// socket.on('offer_status_update', function(data){
//     const offerId = data.offer_id;
//     const status = data.status; // "accepted" vagy "declined"
//     const statusText = status === 'accepted' ? "✔ Elfogadva" : "✖ Elutasítva";
//     const toastMessage = `Ajánlat státusza változott:<br> ${data.origin} - ${data.destination} (${data.price} ${data.currency.toUpperCase()})<br>${statusText}`;
//
//     // Először próbáljuk listában frissíteni
//     socket.on('offer_status_update', function(data){
//         const $offerItem = $(`#offer-${data.offer_id}`);
//         if($offerItem.length){
//             // Státusz osztály frissítése
//             $offerItem.removeClass('status-accepted status-declined status-pending')
//                       .addClass(data.status === 'accepted' ? 'status-accepted'
//                                                             : data.status === 'declined' ? 'status-declined'
//                                                                                           : 'status-pending');
//             // Státusz szöveg
//             const $statusDiv = $offerItem.find('.offer-status');
//             $statusDiv.text(data.status === 'accepted' ? '✅ Elfogadva'
//                                                         : data.status === 'declined' ? '❌ Elutasítva'
//                                                                                       : '');
//         }
//     });
//
//     // Chat ablakban
//     const $chatOffer = $(`.offer-summary[data-offer-id="${offerId}"] .offer-status`);
//     if($chatOffer.length){
//         $chatOffer.text(statusText).css("color", status === 'accepted' ? 'green' : 'red');
//     }
//
//     // Toast, ha nincs sehol
//     if(!$offerItem.length && !$chatOffer.length){
//         showOfferToast(toastMessage, status);
//     }
// });

// SocketIO: másik fél frissítése a gyors ajánlatról
socket.on('offer_updated', function(data){
    const offerId = data.offer_id;
    const updated = data.data;
    const $offerDiv = $(`.offer-summary[data-offer-id="${offerId}"]`);
    if(!$offerDiv.length) return;

    $offerDiv.find('.offer-left span').text(`⬆️${updated.origin}`);
    $offerDiv.find('.offer-right span').text(`${updated.destination}⬇️`);
    $offerDiv.find('.offer-left small b').first().text(updated.pickup_date);
    $offerDiv.find('.offer-right small b').first().text(updated.arrival_date);
    $offerDiv.find('.offer-left b').first().text(`${updated.price} ${updated.currency.toUpperCase()}`);
});
