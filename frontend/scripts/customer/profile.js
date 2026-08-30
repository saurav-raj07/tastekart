const profile$ = selector => document.querySelector(selector);
const profileMoney = value => `₹${Number(value).toLocaleString('en-IN')}`;
const profileEscape = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const profileToken = () => localStorage.getItem('tastekart-auth-token') || '';
let selectedPlace = {};

function renderAddresses(addresses) { profile$('#savedAddresses').innerHTML = addresses.length ? addresses.map(address => `<div class="saved-address" data-address-id="${profileEscape(address.id)}"><span class="address-pin">⌖</span><div><strong>${profileEscape(address.label)}</strong><p>${profileEscape(address.full_address)}</p>${address.landmark ? `<small>Near ${profileEscape(address.landmark)}</small>` : ''}</div><button type="button" class="select-address-button">Select address</button></div>`).join('') : '<p class="empty-address">No saved addresses yet. Add one for faster checkout.</p>'; highlightSelectedProfileAddress(); }
function setupMapplsAutocomplete(enabled) { const input = profile$('#addressSearch'); const help = profile$('#addressHelp'); if (!enabled) { help.textContent = 'Mappls is not configured yet. Enter your complete delivery address manually.'; return; } const dropdown = document.createElement('div'); dropdown.className = 'mappls-suggestions'; input.parentElement.appendChild(dropdown); let timer; input.addEventListener('input', () => { clearTimeout(timer); selectedPlace = {}; const query = input.value.trim(); if (query.length < 2) { dropdown.innerHTML = ''; return; } timer = setTimeout(async () => { try { const response = await fetch(`/api/locations/autosuggest?q=${encodeURIComponent(query)}`); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Address search unavailable'); const suggestions = data.suggestions || []; dropdown.innerHTML = suggestions.map((suggestion, index) => `<button type="button" class="mappls-suggestion" data-suggestion="${index}"><strong>${profileEscape(suggestion.label)}</strong><small>Mappls address result</small></button>`).join(''); dropdown.querySelectorAll('.mappls-suggestion').forEach(button => button.onclick = () => { const suggestion = suggestions[Number(button.dataset.suggestion)]; selectedPlace = {fullAddress:suggestion.label, placeId:suggestion.placeId, latitude:suggestion.latitude, longitude:suggestion.longitude}; input.value = suggestion.label; profile$('#addressCity').value = suggestion.city || ''; profile$('#addressPincode').value = suggestion.pincode || ''; dropdown.innerHTML = ''; }); } catch (error) { help.textContent = error.message; } }, 250); }); document.addEventListener('click', event => { if (!input.parentElement.contains(event.target)) dropdown.innerHTML = ''; }); }
async function loadProfile() { if (!profileToken()) return window.location.replace('/login'); try { const headers = {'Authorization':`Bearer ${profileToken()}`}; const [accountResponse, ordersResponse, configResponse] = await Promise.all([fetch('/api/auth/me', {headers}), fetch('/api/orders', {headers}), fetch('/api/config')]); if (!accountResponse.ok || !ordersResponse.ok) throw new Error('Your session has expired. Please log in again.'); const account = (await accountResponse.json()).account; const orders = (await ordersResponse.json()).orders; const config = await configResponse.json(); profile$('#accountDetails').innerHTML = `<div class="profile-avatar">${profileEscape(account.name[0].toUpperCase())}</div><div class="account-copy"><span class="kicker">CUSTOMER ACCOUNT</span><h2>${profileEscape(account.name)}</h2><p><b>Username</b> ${profileEscape(account.username || account.email || '—')}</p></div>`; renderAddresses(account.addresses || (account.address ? [{label:'Home',full_address:account.address}] : [])); profile$('#orderHistory').innerHTML = orders.length ? orders.map(order => `<article class="history-row"><div class="history-main"><div class="history-heading"><strong>${profileEscape(order.id)}</strong><span class="status-pill">${profileEscape(order.status)}</span></div><p>${order.items.map(item => `${profileEscape(item.name)} × ${item.quantity}`).join(', ')}</p><small>Delivered from ${profileEscape(order.restaurant_id)}</small></div><strong class="history-total">${profileMoney(order.total)}</strong></article>`).join('') : '<div class="empty-history">No orders yet. Your delicious history starts here.</div>'; setupMapplsAutocomplete(config.mapplsEnabled === 'true'); profile$('#profileLoading').hidden = true; profile$('#profileContent').hidden = false; } catch (error) { localStorage.removeItem('tastekart-auth-token'); localStorage.removeItem('tastekart-user-id'); localStorage.removeItem('tastekart-user-name'); profile$('#profileLoading').hidden = true; profile$('#profileError').hidden = false; profile$('#profileError').innerHTML = `${profileEscape(error.message)} <a href="/login">Log in again</a>`; } }
profile$('#addAddressButton').onclick = () => { profile$('#addressForm').hidden = false; profile$('#addAddressButton').hidden = true; profile$('#addressSearch').focus(); };
profile$('#cancelAddress').onclick = () => { profile$('#addressForm').hidden = true; profile$('#addAddressButton').hidden = false; profile$('#addressForm').reset(); selectedPlace = {}; };
profile$('#addressForm').onsubmit = async event => { event.preventDefault(); const fullAddress = selectedPlace.fullAddress || profile$('#addressSearch').value.trim(); try { const response = await fetch('/api/auth/addresses', {method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${profileToken()}`},body:JSON.stringify({label:profile$('#addressLabel').value,fullAddress,house:profile$('#addressHouse').value,landmark:profile$('#addressLandmark').value,city:profile$('#addressCity').value,pincode:profile$('#addressPincode').value,placeId:selectedPlace.placeId || '',latitude:selectedPlace.latitude,longitude:selectedPlace.longitude})}); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Unable to save address'); renderAddresses(data.addresses); profile$('#addressForm').hidden = true; profile$('#addAddressButton').hidden = false; profile$('#addressForm').reset(); selectedPlace = {}; } catch (error) { profile$('#addressHelp').textContent = error.message; } };
profile$('#profileLogout').onclick = async () => { await fetch('/api/auth/logout', {method:'POST',headers:{'Authorization':`Bearer ${profileToken()}`}}); localStorage.removeItem('tastekart-auth-token'); localStorage.removeItem('tastekart-user-id'); localStorage.removeItem('tastekart-user-name'); window.location.replace('/login'); };
loadProfile();

function highlightSelectedProfileAddress() {
    const selectedLabel = localStorage.getItem('tastekart-selected-address-label');
    profile$('#savedAddresses')?.querySelectorAll('.saved-address').forEach(card => {
        const isSelected = card.querySelector('strong')?.textContent?.trim() === selectedLabel;
        card.classList.toggle('selected', isSelected);
        const button = card.querySelector('.select-address-button');
        if (button) button.textContent = isSelected ? 'Selected address' : 'Select address';
    });
}

document.addEventListener('click', event => {
    const button = event.target.closest('.select-address-button');
    if (!button) return;
    const card = button.closest('.saved-address');
    if (!card) return;
    const label = card.querySelector('strong')?.textContent?.trim();
    const fullAddress = card.querySelector('p')?.textContent?.trim();
    if (!label) return;
    if (card.dataset.addressId) localStorage.setItem('tastekart-selected-address-id', card.dataset.addressId);
    else localStorage.removeItem('tastekart-selected-address-id');
    localStorage.setItem('tastekart-selected-address-label', label);
    if (fullAddress) localStorage.setItem('tastekart-selected-address-text', fullAddress);
    highlightSelectedProfileAddress();
});

let showAllOrders = false;

function decorateOrderHistory() {
    const container = profile$('#orderHistory');
    if (!container) return;
    const rows = [...container.querySelectorAll('.history-row')];
    rows.forEach((row, index) => {
        const isOlder = index >= 5 && !showAllOrders;
        row.classList.toggle('older-order', isOlder);
        row.hidden = isOlder;
        const pill = row.querySelector('.status-pill');
        const status = pill?.textContent?.trim().toUpperCase() || '';
        row.classList.remove('status-delivered', 'status-confirmed', 'status-other');
        row.classList.add(status === 'DELIVERED' ? 'status-delivered' : status === 'CONFIRMED' ? 'status-confirmed' : 'status-other');
        if (pill) pill.textContent = status || 'UNKNOWN';
    });
    let moreButton = container.querySelector('.more-orders-button');
    if (rows.length > 5 && !moreButton && !showAllOrders) {
        moreButton = document.createElement('button');
        moreButton.type = 'button';
        moreButton.className = 'more-orders-button';
        const buttonLabel = showAllOrders ? 'Less orders' : 'More orders';
        if (moreButton.textContent !== buttonLabel) moreButton.textContent = buttonLabel;
        moreButton.onclick = () => {
            showAllOrders = !showAllOrders;
            decorateOrderHistory();
        };
        container.appendChild(moreButton);
    } else if (moreButton) {
        const buttonLabel = showAllOrders ? 'Less orders' : 'More orders';
        if (moreButton.textContent !== buttonLabel) moreButton.textContent = buttonLabel;
    }
}

const orderHistoryObserver = new MutationObserver(decorateOrderHistory);
orderHistoryObserver.observe(profile$('#orderHistory'), {childList: true});
