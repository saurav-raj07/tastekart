let selectedRestaurant = '';
let dashboard = null;
let currentPartnerSlug = '';
const $ = selector => document.querySelector(selector);
const partnerSlug = () => decodeURIComponent(location.pathname.split('/').filter(Boolean)[1] || '');
const slugify = value => String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'partner';
const partnerTokenKey = () => `tastekart-partner-token:${partnerSlug() || 'generic'}`;
const token = () => {
  const routeKey = partnerSlug().replaceAll('-', '');
  const matchingKey = Object.keys(localStorage).find(key => key.startsWith('tastekart-partner-token:') && key.split(':').pop().replaceAll('-', '') === routeKey);
  return localStorage.getItem(partnerTokenKey()) || (matchingKey ? localStorage.getItem(matchingKey) : '') || localStorage.getItem('tastekart-partner-token') || '';
};
const money = value => `₹${Number(value).toLocaleString('en-IN')}`;
const escapeHtml = value => String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
function renderRestaurantBrand(restaurant) { const el = $('#restaurantBrand'); if (!restaurant) { el.hidden = true; return; } const name = restaurant.name || 'Restaurant'; const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase(); el.innerHTML = `${restaurant.image_url ? `<img src="${escapeHtml(restaurant.image_url)}" alt="${escapeHtml(name)} logo"/>` : `<span class="restaurant-brand-fallback">${escapeHtml(initials || 'R')}</span>`}<span>${escapeHtml(name)}</span>`; el.hidden = false; }
function renderPartnerAvatar(account) { const el = $('.avatar'); const initials = (account.name || 'P').split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('').toUpperCase(); el.innerHTML = account.logo_url ? `<img src="${escapeHtml(account.logo_url)}" alt="${escapeHtml(account.name || 'Partner')} logo"/>` : escapeHtml(initials || 'P'); }
function showPartnerProfile(identity) { if ($('#partnerProfileModal')) { $('#partnerProfileModal').remove(); return; } document.body.insertAdjacentHTML('beforeend', `<div class="partner-auth" id="partnerProfileModal"><div class="partner-auth-card"><button class="close-btn" id="closePartnerProfile">×</button><span class="eyebrow">PARTNER ACCOUNT</span><h2>Edit profile</h2><p>Update the details used to access your partner workspace.</p><form id="partnerProfileForm"><label>Partner name<input id="profileName" required value="${escapeHtml(identity.account.name || '')}"/></label><label>Email address<input id="profileEmail" type="email" required value="${escapeHtml(identity.account.email || '')}"/></label><label>Partner logo URL<input id="profileLogo" type="url" value="${escapeHtml(identity.account.logo_url || '')}" placeholder="https://..."/></label><label>New password<input id="profilePassword" type="password" minlength="6" placeholder="Leave blank to keep current password"/></label><button class="primary" type="submit">Save changes <span>→</span></button></form><p id="partnerProfileMessage" class="profile-form-message"></p></div></div>`); $('#closePartnerProfile').onclick = () => $('#partnerProfileModal').remove(); $('#partnerProfileForm').onsubmit = async event => { event.preventDefault(); const message = $('#partnerProfileMessage'); try { const response = await request('/api/partner/profile', {method:'PATCH',body:JSON.stringify({name:$('#profileName').value,email:$('#profileEmail').value,logoUrl:$('#profileLogo').value,password:$('#profilePassword').value || null})}); localStorage.setItem(`tastekart-partner-token:${slugify(response.partner.name)}`, token()); if (partnerSlug() !== slugify(response.partner.name)) { location.assign(`/partner/${encodeURIComponent(slugify(response.partner.name))}`); return; } $('#partnerAccountLabel').textContent = response.partner.name; renderPartnerAvatar(response.partner); $('#partnerProfileModal').remove(); toast('Profile updated'); } catch (error) { message.textContent = error.message; } }; }
const toast = message => { const el = $('#toast'); el.textContent = message; el.classList.add('show'); clearTimeout(window.toastTimer); window.toastTimer = setTimeout(() => el.classList.remove('show'), 2400); };
async function request(url, options = {}) { const headers = {'Content-Type':'application/json', ...(options.headers || {})}; if (token()) headers.Authorization = `Bearer ${token()}`; const response = await fetch(url, {...options, headers}); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Something went wrong'); return data; }
function showAuth() { if ($('#partnerAuth')) return; document.body.insertAdjacentHTML('beforeend', `<div class="partner-auth" id="partnerAuth"><div class="partner-auth-card"><span class="eyebrow">TASTEKART PARTNERS</span><h2 id="partnerAuthTitle">Welcome, partner</h2><p id="partnerAuthMessage">Log in to manage your restaurant, or create a partner account to get started.</p><form id="partnerAuthForm"><input id="partnerAuthName" placeholder="Your name / business owner"/><input id="partnerAuthEmail" type="email" required placeholder="Email address"/><input id="partnerAuthPassword" type="password" required minlength="6" placeholder="Password (6+ characters)"/><button class="primary" type="submit">Log in <span>→</span></button></form><button class="partner-auth-switch" id="partnerAuthSwitch">New partner? Create an account</button></div></div>`); let register = false; const name = $('#partnerAuthName'); $('#partnerAuthSwitch').onclick = () => { register = !register; name.hidden = !register; name.required = register; $('#partnerAuthTitle').textContent = register ? 'Create your partner account' : 'Welcome, partner'; $('#partnerAuthForm button').innerHTML = register ? 'Create account <span>→</span>' : 'Log in <span>→</span>'; $('#partnerAuthSwitch').textContent = register ? 'Already registered? Log in' : 'New partner? Create an account'; }; name.hidden = true; $('#partnerAuthForm').onsubmit = async event => { event.preventDefault(); try { const endpoint = register ? '/api/partner/auth/register' : '/api/partner/auth/login'; const response = await request(endpoint, {method:'POST',body:JSON.stringify({name:name.value,email:$('#partnerAuthEmail').value,password:$('#partnerAuthPassword').value})}); localStorage.setItem(`tastekart-partner-token:${slugify(response.partner.name)}`, response.token); localStorage.removeItem('tastekart-partner-token'); location.assign(`/partner/${encodeURIComponent(slugify(response.partner.name))}`); } catch (error) { $('#partnerAuthMessage').textContent = error.message; } }; }
async function loadRestaurants() { try { const identity = await request('/api/auth/me'); const identitySlug = slugify(identity.account.name); if (partnerSlug() !== identitySlug) { location.replace(`/partner/${encodeURIComponent(identitySlug)}`); return; } $('#partnerLogout').hidden = false; $('#refreshWorkspace').hidden = false; renderPartnerAvatar(identity.account); $('#partnerAccountLabel').textContent = identity.account.name || 'Partner workspace'; const data = await request('/api/partner/restaurants'); $('#restaurantSelect').innerHTML = data.restaurants.length ? data.restaurants.map(r => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('') : '<option value="">No restaurants yet</option>'; selectedRestaurant = data.restaurants[0]?.id || ''; renderOnboardingButton(); if (selectedRestaurant) await loadDashboard(); else showOnboarding(); } catch (error) { if (error.message === 'Login required' || error.message === 'Partner login required') showAuth(); else toast(error.message); } }
function syncSidebar() { if (!dashboard) return; const active = dashboard.orders.filter(order => !['DELIVERED','CANCELLED'].includes(order.status)).length; $('#sidebarOrderCount').textContent = active; $('#sidebarOrderCount').classList.toggle('has-active-orders', active > 0); const store = document.querySelector('.sidebar-store'); const open = dashboard.restaurant.is_open; $('#sidebarStatus').textContent = open ? 'Open' : 'Closed'; store.classList.toggle('is-open', open); store.classList.toggle('is-closed', !open); localStorage.setItem(`tastekart-status:${slugify(dashboard.restaurant.name).replaceAll('-', '')}`, open ? 'open' : 'closed'); $('#sidebarToggleStatus').textContent = open ? 'Close restaurant' : 'Open restaurant'; }
async function loadDashboard() { if (!selectedRestaurant) return; $('#editProfile').hidden = false; dashboard = await request(`/api/partner/restaurants/${selectedRestaurant}`); renderRestaurantBrand(dashboard.restaurant); renderStatus(); renderMetrics(); renderRestaurantAnalytics(); renderMenu(); renderOrders(); syncSidebar(); }
function renderOnboardingButton() { if ($('#onboardButton')) return; $('.partner-heading').insertAdjacentHTML('beforeend', '<button class="primary onboard-button" id="onboardButton">＋ Onboard restaurant</button>'); $('#onboardButton').onclick = showOnboarding; }
function showOnboarding() { if ($('#onboardingModal')) return; document.body.insertAdjacentHTML('beforeend', `<div class="partner-auth" id="onboardingModal"><div class="partner-auth-card"><button class="close-btn" id="closeOnboarding">×</button><span class="eyebrow">NEW RESTAURANT</span><h2>Onboard your restaurant</h2><p>Add your storefront details. You can add the menu after onboarding.</p><form id="onboardingForm"><input id="restaurantName" required placeholder="Restaurant name"/><input id="restaurantCuisine" required placeholder="Cuisine (e.g. Indian · Bowls)"/><input id="restaurantDelivery" placeholder="Delivery time (e.g. 25–35 min)" value="25–35 min"/><input id="restaurantImage" type="url" placeholder="Image URL (optional)"/><textarea id="restaurantDescription" placeholder="Short description (optional)"></textarea><button class="primary" type="submit">Create restaurant <span>→</span></button></form></div></div>`); $('#closeOnboarding').onclick = () => $('#onboardingModal').remove(); $('#onboardingForm').onsubmit = async event => { event.preventDefault(); try { const data = await request('/api/partner/restaurants', {method:'POST',body:JSON.stringify({name:$('#restaurantName').value,cuisine:$('#restaurantCuisine').value,deliveryMinutes:$('#restaurantDelivery').value,imageUrl:$('#restaurantImage').value,description:$('#restaurantDescription').value})}); $('#onboardingModal').remove(); toast('Restaurant onboarded'); await loadRestaurants(); selectedRestaurant = data.restaurant.id; $('#restaurantSelect').value = selectedRestaurant; await loadDashboard(); } catch (error) { toast(error.message); } }; }
function renderStatus() { const open = dashboard.restaurant.is_open; $('#statusBanner').classList.toggle('closed', !open); $('#statusText').textContent = open ? 'Open for orders' : 'Restaurant is closed'; $('#statusHint').textContent = open ? 'Customers can discover and order from you.' : 'Customers will see that you are not accepting orders.'; $('#toggleStatus').textContent = open ? 'Close restaurant' : 'Open restaurant'; }
function renderMetrics() { if (isRestaurantPage) { const totalOrders = dashboard.orders.length; const salesOrders = dashboard.orders.filter(order => order.status !== 'CANCELLED').length; const totalSales = dashboard.orders.filter(order => order.status !== 'CANCELLED').reduce((sum, order) => sum + Number(order.total), 0); $('#metrics').innerHTML = `<div class="metric restaurant-stat"><span>Total orders</span><strong>${totalOrders}</strong></div><div class="metric restaurant-stat"><span>Sales orders</span><strong>${salesOrders}</strong></div><div class="metric restaurant-stat sales-total"><span>Total sales</span><strong>${money(totalSales)}</strong></div>`; return; } const active = dashboard.orders.filter(order => !['DELIVERED','CANCELLED'].includes(order.status)).length; const completed = dashboard.orders.filter(order => order.status === 'DELIVERED').length; $('#metrics').innerHTML = `<div class="metric active-orders-metric ${active ? 'has-active-orders' : ''}"><span>Active orders</span><strong>${active}</strong></div><div class="metric completed-orders-metric"><span>Completed orders</span><strong>${completed}</strong></div>`; }
function renderMenu() { $('#menuList').innerHTML = dashboard.menu.length ? dashboard.menu.map(item => `<div class="menu-row"><span class="dish-icon">${item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt=""/>` : escapeHtml(item.emoji || '🍽️')}</span><div><div class="dish-name">${escapeHtml(item.name)}</div><div class="dish-price">${money(item.price)}</div></div><div class="dish-actions"><button class="availability ${item.available ? '' : 'off'}" data-availability="${item.id}">${item.available ? 'Available' : 'Hidden'}</button><button class="remove-item" title="Remove item" data-remove="${item.id}">×</button></div></div>`).join('') : '<div class="empty-state">No menu items yet. Add your first dish above.</div>'; document.querySelectorAll('[data-availability]').forEach(button => button.onclick = () => toggleItem(Number(button.dataset.availability))); document.querySelectorAll('[data-remove]').forEach(button => button.onclick = () => removeItem(Number(button.dataset.remove))); }
function renderOrders() { const columns = [{key:'new',title:'New orders',statuses:['PLACED','CONFIRMED'],next:'PREPARING',action:'Start preparing'},{key:'preparing',title:'Preparing',statuses:['PREPARING'],next:'READY',action:'Mark ready'},{key:'ready',title:'Ready for pickup',statuses:['READY','OUT_FOR_DELIVERY'],next:'DELIVERED',action:'Mark completed'},{key:'completed',title:'Completed',statuses:['DELIVERED','CANCELLED'],next:null,action:null}]; $('#ordersList').innerHTML = columns.map(column => { const orders = dashboard.orders.filter(order => column.statuses.includes(order.status)); return `<section class="order-column"><div class="order-column-head"><span>${column.title}</span><b>${orders.length}</b></div>${orders.length ? orders.map(order => `<article class="order-card"><div class="order-top"><span class="order-id">${escapeHtml(order.id)}</span><span class="order-time">${new Date(order.created_at * 1000).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'})}</span></div><strong class="order-customer">${escapeHtml(order.customer_name || order.user_name || 'Customer')}</strong><div class="order-items">${order.items.map(item => `${item.quantity}× ${escapeHtml(item.name)}`).join(' · ')}</div><div class="order-bottom"><strong>${money(order.total)}</strong>${column.next ? `<button class="order-advance" data-order="${escapeHtml(order.id)}" data-next="${column.next}">${column.action} →</button>` : ''}</div></article>`).join('') : '<div class="order-column-empty">No orders</div>'}</section>`; }).join(''); document.querySelectorAll('.order-advance').forEach(button => button.onclick = () => updateOrder(button.dataset.order, button.dataset.next)); }
async function toggleItem(id) { const item = dashboard.menu.find(entry => entry.id === id); try { await request(`/api/partner/menu/${id}`, {method:'PATCH',body:JSON.stringify({available:!item.available})}); toast(item.available ? 'Item hidden from customers' : 'Item is live again'); await loadDashboard(); } catch (error) { toast(error.message); } }
async function removeItem(id) { if (!confirm('Remove this item from the menu?')) return; try { await request(`/api/partner/menu/${id}`, {method:'DELETE'}); toast('Menu item removed'); await loadDashboard(); } catch (error) { toast(error.message); } }
async function updateOrder(id, status) { try { await request(`/api/partner/orders/${id}/status`, {method:'PATCH',body:JSON.stringify({status,restaurantId:selectedRestaurant})}); toast(`Order updated to ${status.replaceAll('_',' ').toLowerCase()}`); await loadDashboard(); } catch (error) { toast(error.message); await loadDashboard(); } }
$('#restaurantSelect').onchange = async event => { selectedRestaurant = event.target.value; await loadDashboard(); };
$('#toggleStatus').onclick = async () => { const banner = $('#statusBanner'); banner.classList.remove('status-clicked'); void banner.offsetWidth; banner.classList.add('status-clicked'); try { await request(`/api/partner/restaurants/${selectedRestaurant}/status`, {method:'PATCH',body:JSON.stringify({isOpen:!dashboard.restaurant.is_open})}); toast(dashboard.restaurant.is_open ? 'Restaurant closed' : 'Restaurant is open'); await loadDashboard(); } catch (error) { toast(error.message); } };
$('#refreshOrders').onclick = loadDashboard; $('#showAdd').onclick = () => { $('#addForm').hidden = false; $('#itemName').focus(); }; $('#cancelAdd').onclick = () => { $('#addForm').reset(); $('#addForm').hidden = true; };
$('#addForm').onsubmit = async event => { event.preventDefault(); try { await request(`/api/partner/restaurants/${selectedRestaurant}/menu`, {method:'POST',body:JSON.stringify({name:$('#itemName').value,price:$('#itemPrice').value,emoji:$('#itemEmoji').value || '🍽️',imageUrl:$('#itemImage').value})}); $('#addForm').reset(); $('#addForm').hidden = true; toast('New dish added'); await loadDashboard(); } catch (error) { toast(error.message); } };
$('#partnerLogout').onclick = async () => { try { await request('/api/auth/logout', {method:'POST'}); } catch (_) {} localStorage.removeItem(partnerTokenKey()); localStorage.removeItem('tastekart-partner-token'); localStorage.removeItem('tastekart-partner-name'); location.assign('/partner'); };
const authStyle = document.createElement('style'); authStyle.textContent = `.partner-auth{position:fixed;inset:0;background:#241b1866;display:grid;place-items:center;padding:20px;z-index:10}.partner-auth-card{position:relative;width:min(460px,100%);background:#fffefa;border-radius:20px;padding:30px;box-shadow:0 25px 80px #241b1840}.partner-auth-card h2{font-size:25px;margin:10px 0}.partner-auth-card p{color:#867a70;font-size:12px;line-height:1.6;margin:0 0 20px}.partner-auth-card form{display:grid;gap:9px}.partner-auth-card input,.partner-auth-card textarea{width:100%;border:1px solid #e8dfd4;border-radius:9px;padding:12px;font-size:12px}.partner-auth-card textarea{min-height:80px;resize:vertical}.partner-auth-switch{border:0;background:none;color:#e95732;font-size:11px;font-weight:700;margin:18px auto 0;display:block;cursor:pointer}.onboard-button{align-self:end}`; document.head.appendChild(authStyle);
const authBackdropStyle = document.createElement('style'); authBackdropStyle.textContent = '.partner-auth{background:#f8f4ee}'; document.head.appendChild(authBackdropStyle);
const partnerUiStyle = document.createElement('style'); partnerUiStyle.textContent = '.dish-icon img{width:100%;height:100%;object-fit:cover;border-radius:11px}.partner-logout{border:1px solid #e8dfd4;background:#fff;border-radius:9px;color:#e95732;padding:8px 10px;font-size:10px;font-weight:800;cursor:pointer}.onboard-button{align-self:end}.add-form{grid-template-columns:1.4fr .6fr .45fr 1.2fr auto auto}'; document.head.appendChild(partnerUiStyle);
async function loadProfileRestaurants() { const card = $('#partnerProfileModal .partner-auth-card'); if (!card) return; try { const data = await request('/api/partner/restaurants'); const section = document.createElement('section'); section.className = 'profile-restaurants'; section.innerHTML = `<span class="eyebrow">YOUR RESTAURANTS</span><div>${data.restaurants.length ? data.restaurants.map(row => `<div class="profile-restaurant-row"><span>${escapeHtml(row.name)}</span><button class="danger-button" data-profile-delete-restaurant="${escapeHtml(row.id)}">Delete</button></div>`).join('') : '<p class="profile-empty">No restaurants onboarded.</p>'}</div>`; card.insertBefore(section, $('#deletePartnerProfile')); section.querySelectorAll('[data-profile-delete-restaurant]').forEach(button => button.onclick = async () => { if (!confirm('Delete this restaurant, its menu, and its orders? This cannot be undone.')) return; try { await request(`/api/partner/restaurants/${button.dataset.profileDeleteRestaurant}`, {method:'DELETE'}); toast('Restaurant deleted'); button.closest('.profile-restaurant-row').remove(); if (button.dataset.profileDeleteRestaurant === selectedRestaurant) { selectedRestaurant = ''; dashboard = null; await loadRestaurants(); } } catch (error) { toast(error.message); } }); } catch (error) { toast(error.message); } }
async function refreshWorkspace() { const currentRestaurant = selectedRestaurant; try { await loadRestaurants(); if (currentRestaurant && [...$('#restaurantSelect').options].some(option => option.value === currentRestaurant)) { selectedRestaurant = currentRestaurant; $('#restaurantSelect').value = currentRestaurant; await loadDashboard(); } toast('Workspace refreshed'); } catch (error) { toast(error.message); } }
$('#refreshWorkspace').onclick = refreshWorkspace;
document.querySelectorAll('.side-nav').forEach(button => button.onclick = () => { const target = document.getElementById(button.dataset.section) || document.getElementById(button.dataset.section === 'restaurant-control' ? 'statusBanner' : button.dataset.section); if (target) target.scrollIntoView({behavior:'smooth', block:'start'}); document.querySelectorAll('.side-nav').forEach(item => item.classList.remove('active')); button.classList.add('active'); });
$('#sidebarToggleStatus').onclick = () => $('#toggleStatus').click();
$('#editProfile').onclick = async () => { try { showPartnerProfile(await request('/api/auth/me')); setTimeout(() => { const card = $('#partnerProfileModal .partner-auth-card'); if (card && !$('#deletePartnerProfile')) { card.insertAdjacentHTML('beforeend', '<button id="deletePartnerProfile" class="danger-button profile-delete">Delete partner profile</button>'); $('#deletePartnerProfile').onclick = deletePartnerProfile; loadProfileRestaurants(); } }, 0); } catch (error) { toast(error.message); } };
async function deletePartnerProfile() { if (!confirm('Delete your partner profile, restaurants, menus, and orders? This cannot be undone.')) return; try { await request('/api/partner/profile', {method:'DELETE'}); localStorage.removeItem(partnerTokenKey()); localStorage.removeItem('tastekart-partner-token'); location.assign('/partner'); } catch (error) { toast(error.message); } }
const routeParts = location.pathname.split('/').filter(Boolean);
const partnerSection = routeParts.length === 3 ? routeParts[2] : 'orders';
const isMenuPage = partnerSection === 'menu';
const isRestaurantPage = partnerSection === 'restaurant';
const restaurantPath = () => routeParts.length === 3 ? routeParts[1] : '';
const partnerPathForDashboard = () => currentPartnerSlug || partnerSlug();
const routeStyle = document.createElement('style');
routeStyle.textContent = '.dashboard-page .menu-panel,.restaurant-page .menu-panel,.restaurant-page .orders-panel,.restaurant-page #metrics,.dashboard-page .sidebar-store,.dashboard-page .status-banner,.menu-page .sidebar-store,.menu-page .status-banner,.menu-page #metrics,.menu-page .orders-panel{display:none}.menu-page .partner-grid,.restaurant-page .partner-grid{display:block}.menu-page .menu-panel{width:100%;max-width:900px;margin:0 auto}.restaurant-page .status-banner{display:flex;max-width:900px;margin-left:auto;margin-right:auto}.dashboard-page .metrics{grid-template-columns:repeat(2,minmax(0,280px));gap:28px;justify-content:start}.active-orders-metric.has-active-orders{border:2px solid #e95732;background:#fff5f0;animation:active-orders-pulse 1.1s ease-in-out infinite}.active-orders-metric.has-active-orders strong{color:#e95732}.completed-orders-metric{border-color:#b9d4bc;background:#f0f8ef}.completed-orders-metric strong{color:#4c8059}.side-nav b.has-active-orders{position:relative;z-index:1;animation:sidebar-order-pulse .9s ease-in-out infinite}@keyframes active-orders-pulse{0%,100%{transform:scale(1);box-shadow:0 0 0 0 #e9573270}50%{transform:scale(1.045);box-shadow:0 0 0 13px #e9573200}}@keyframes sidebar-order-pulse{0%,100%{box-shadow:0 0 0 0 #e95732b0,0 0 0 0 #e9573260;background:#e95732}45%{box-shadow:0 0 0 9px #e9573250,0 0 0 18px #e957321c;background:#ff704b}100%{box-shadow:0 0 0 19px #e9573200,0 0 0 28px #e9573200;background:#e95732}}@media(max-width:650px){.dashboard-page .metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}#refreshWorkspace{display:none}.refresh-clicked{animation:refresh-spin .45s ease-in-out}@keyframes refresh-spin{50%{transform:rotate(180deg) scale(1.08);opacity:.55}100%{transform:rotate(360deg)}}';
document.head.appendChild(routeStyle);
const routeRefreshStyle = document.createElement('style');
routeRefreshStyle.textContent = '.restaurant-page #refreshWorkspace{display:inline-flex}.side-nav b:not(.has-active-orders){display:none}';
document.head.appendChild(routeRefreshStyle);
const analyticsRouteStyle = document.createElement('style');
analyticsRouteStyle.textContent = '.dashboard-page .restaurant-analytics,.menu-page .restaurant-analytics{display:none}';
document.head.appendChild(analyticsRouteStyle);
const staticPulseStyle = document.createElement('style');
staticPulseStyle.textContent = '@keyframes active-orders-pulse{0%,100%{box-shadow:0 0 0 0 #e9573270}50%{box-shadow:0 0 0 15px #e9573200}}';
document.head.appendChild(staticPulseStyle);
const menuLayoutStyle = document.createElement('style');
menuLayoutStyle.textContent = '.add-form[hidden]{display:none}.menu-page .menu-panel{width:50%;max-width:none;margin-left:0;margin-right:auto}.menu-page .menu-row{grid-template-columns:72px 1fr auto}.menu-page .dish-icon{width:72px;height:72px;font-size:34px}@media(max-width:850px){.menu-page .menu-panel{width:100%}}';
document.head.appendChild(menuLayoutStyle);
const foodMarkStyle = document.createElement('style');
foodMarkStyle.textContent = '.food-mark{display:inline-grid;place-items:center;width:16px;height:16px;margin-left:7px;border:1px solid currentColor;border-radius:3px;vertical-align:middle}.food-mark:after{content:"";display:block}.food-mark.veg{color:#4c8059}.food-mark.veg:after{width:7px;height:7px;border-radius:50%;background:currentColor}.food-mark.non-veg{color:#c74632}.food-mark.non-veg:after{width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-bottom:8px solid currentColor}.add-form select{width:100%;border:1px solid #e8dfd4;border-radius:9px;padding:10px;font-size:11px;background:#fff;outline-color:#e95732}';
document.head.appendChild(foodMarkStyle);
const restaurantStatsStyle = document.createElement('style');
restaurantStatsStyle.textContent = '.restaurant-page .status-banner{margin-left:0;margin-right:auto}.restaurant-page .metrics{display:grid;grid-template-columns:repeat(3,minmax(0,280px));gap:20px;justify-content:start;margin:18px 0}.restaurant-stat{background:#fffefa}.restaurant-stat.sales-total{border-color:#b9d4bc;background:#f0f8ef}.restaurant-stat.sales-total strong{color:#4c8059}.status-clicked{animation:status-panel-pulse .65s ease-in-out}@keyframes status-panel-pulse{0%{box-shadow:0 0 0 0 #4c805980}45%{box-shadow:0 0 0 12px #4c80591c}100%{box-shadow:0 0 0 0 #4c805900}}@media(max-width:850px){.restaurant-page .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}';
document.head.appendChild(restaurantStatsStyle);
const restaurantStatsVisibilityStyle = document.createElement('style');
restaurantStatsVisibilityStyle.textContent = '.restaurant-page #metrics{display:grid!important}';
document.head.appendChild(restaurantStatsVisibilityStyle);
const sidebarStatusStyle = document.createElement('style');
sidebarStatusStyle.textContent = '.dashboard-page .sidebar-store,.menu-page .sidebar-store{display:block}.dashboard-page .sidebar-store button,.menu-page .sidebar-store button{display:none}';
document.head.appendChild(sidebarStatusStyle);
const sidebarStatusPositionStyle = document.createElement('style');
sidebarStatusPositionStyle.textContent = '.sidebar-store{order:1;margin-top:30px}.sidebar-nav{order:2;margin-top:18px}.sidebar-store button{display:none}.sidebar-store.is-open strong{color:#7fbd86}.sidebar-store.is-closed strong{color:#ef6a55}.sidebar-store.is-closed{background:#3a2927}';
document.head.appendChild(sidebarStatusPositionStyle);
const sidebarStatusVisualStyle = document.createElement('style');
sidebarStatusVisualStyle.textContent = '.sidebar-store strong{font-size:19px;font-weight:900;letter-spacing:.3px;text-transform:uppercase}.sidebar-store.is-open strong{color:#62ff83;text-shadow:0 0 5px #62ff83,0 0 14px #62ff8375}.sidebar-store.is-closed strong{color:#ff5f52;text-shadow:0 0 5px #ff5f52,0 0 14px #ff5f5275}.sidebar-store.is-open,.sidebar-store.is-closed{transition:none}';
document.head.appendChild(sidebarStatusVisualStyle);
function configurePartnerRoute() {
  document.body.classList.toggle('menu-page', isMenuPage);
  document.body.classList.toggle('restaurant-page', isRestaurantPage);
  document.body.classList.toggle('dashboard-page', !isMenuPage && !isRestaurantPage);
  document.querySelector('.restaurant-picker')?.remove();
  document.querySelector('.onboard-button')?.remove();
  const sidebarRefreshButton = $('#refreshWorkspace');
  if (sidebarRefreshButton) { document.querySelector('.partner-sidebar')?.appendChild(sidebarRefreshButton); sidebarRefreshButton.hidden = false; }
  const cachedStatus = localStorage.getItem(`tastekart-status:${restaurantPath().replaceAll('-', '')}`);
  if (cachedStatus) { const store = document.querySelector('.sidebar-store'); const open = cachedStatus === 'open'; $('#sidebarStatus').textContent = open ? 'Open' : 'Closed'; store.classList.toggle('is-open', open); store.classList.toggle('is-closed', !open); }
  const menuButton = document.querySelector('.side-nav[data-section="menu-panel"]');
  const ordersButton = document.querySelector('.side-nav[data-section="orders-panel"]');
  const restaurantButton = document.querySelector('.side-nav[data-section="restaurant-control"]');
  const refreshButton = $('#refreshOrders');
  if (refreshButton) refreshButton.onclick = () => { refreshButton.classList.remove('refresh-clicked'); void refreshButton.offsetWidth; refreshButton.classList.add('refresh-clicked'); setTimeout(() => location.reload(), 450); };
  const restaurantRefreshButton = $('#refreshWorkspace');
  if (restaurantRefreshButton) restaurantRefreshButton.onclick = () => { restaurantRefreshButton.classList.remove('refresh-clicked'); void restaurantRefreshButton.offsetWidth; restaurantRefreshButton.classList.add('refresh-clicked'); setTimeout(() => location.reload(), 450); };
  if (menuButton) {
    menuButton.onclick = () => {
      const restaurantSlug = slugify(dashboard?.restaurant?.name || restaurantPath() || currentPartnerSlug);
      location.assign(`/partner/${encodeURIComponent(restaurantSlug)}/menu`);
    };
    menuButton.classList.toggle('active', isMenuPage);
  }
  if (ordersButton) {
    ordersButton.onclick = () => (isMenuPage || isRestaurantPage) ? location.assign(`/partner/${encodeURIComponent(slugify(dashboard?.restaurant?.name || restaurantPath() || currentPartnerSlug))}/orders`) : document.querySelector('.orders-panel')?.scrollIntoView({behavior:'smooth', block:'start'});
    ordersButton.classList.toggle('active', !isMenuPage && !isRestaurantPage);
  }
  if (restaurantButton) {
    restaurantButton.onclick = () => (isMenuPage || !isRestaurantPage) ? location.assign(`/partner/${encodeURIComponent(slugify(dashboard?.restaurant?.name || restaurantPath() || currentPartnerSlug))}/restaurant`) : document.getElementById('statusBanner')?.scrollIntoView({behavior:'smooth', block:'start'});
    restaurantButton.classList.toggle('active', isRestaurantPage);
  }
  if (isMenuPage || isRestaurantPage) {
    const heading = document.querySelector('.partner-heading h1');
    const description = document.querySelector('.partner-heading p');
    if (isMenuPage) {
      if (heading) heading.innerHTML = 'Keep your menu<br/><em>fresh and tempting.</em>';
      if (description) description.textContent = 'Add dishes, update availability, or remove items from your restaurant menu.';
    } else {
      if (heading) heading.innerHTML = 'Manage your<br/><em>restaurant.</em>';
      if (description) description.textContent = 'Control your restaurant status and keep customers informed.';
    }
  }
}
async function loadRestaurants() {
  try {
    const identity = await request('/api/auth/me');
    currentPartnerSlug = slugify(identity.account.name);
    document.title = `${identity.account.name || 'Partner'} | TasteKart Partner`;
    $('#partnerLogout').hidden = false;
    document.querySelector('.restaurant-picker')?.remove();
    renderPartnerAvatar(identity.account);
    $('#partnerAccountLabel').textContent = identity.account.name || 'Partner workspace';
    const data = await request('/api/partner/restaurants');
    const requestedRestaurant = restaurantPath();
    const normalizedRestaurantPath = requestedRestaurant.replaceAll('-', '');
    const routeRestaurant = data.restaurants.find(row => slugify(row.name) === requestedRestaurant || slugify(row.name).replaceAll('-', '') === normalizedRestaurantPath);
    if (routeParts.length === 3 && !routeRestaurant) {
      selectedRestaurant = '';
      $('#menuList').innerHTML = '<div class="empty-state">This restaurant is not available for the signed-in partner account.</div>';
      $('#ordersList').innerHTML = '<div class="order-column-empty">This restaurant is not available for the signed-in partner account.</div>';
      return;
    }
    selectedRestaurant = (routeRestaurant || data.restaurants[0])?.id || '';
    if (data.restaurants.length && routeParts.length < 3) {
      location.replace(`/partner/${encodeURIComponent(slugify(data.restaurants[0].name))}/orders`);
      return;
    }
    if (selectedRestaurant) await loadDashboard(); else showOnboarding();
  } catch (error) {
    if (error.message === 'Login required' || error.message === 'Partner login required') showAuth(); else toast(error.message);
  }
}
function foodMark(item) { const nonVeg = item.food_type === 'non-veg'; return `<span class="food-mark ${nonVeg ? 'non-veg' : 'veg'}" title="${nonVeg ? 'Non-vegetarian' : 'Vegetarian'}" aria-label="${nonVeg ? 'Non-vegetarian' : 'Vegetarian'}"></span>`; }
function renderRestaurantAnalytics() {
  const section = $('#restaurantAnalytics');
  if (!section) return;
  section.style.display = isRestaurantPage ? 'block' : 'none';
  if (!isRestaurantPage || !dashboard) return;
  const completed = dashboard.orders.filter(order => ['DELIVERED', 'CANCELLED'].includes(order.status));
  const today = new Date();
  const isToday = order => new Date(order.created_at * 1000).toDateString() === today.toDateString();
  const deliveredToday = completed.filter(order => order.status === 'DELIVERED' && isToday(order));
  const salesOrders = dashboard.orders.filter(order => order.status !== 'CANCELLED' && isToday(order));
  const hourlySales = Array.from({length: 24}, () => 0);
  salesOrders.forEach(order => {
    const date = new Date(order.created_at * 1000);
    if (date.toDateString() === today.toDateString()) hourlySales[date.getHours()] += Number(order.total) || 0;
  });
  const salesByHour = hourlySales.map((_, hour) => hourlySales.slice(0, hour + 1).reduce((sum, amount) => sum + amount, 0));
  const chartWidth = 960;
  const chartHeight = 300;
  const chartPadding = {top: 24, right: 18, bottom: 52, left: 78};
  const maxSales = Math.max(...salesByHour, 1);
  const plotWidth = chartWidth - chartPadding.left - chartPadding.right;
  const plotHeight = chartHeight - chartPadding.top - chartPadding.bottom;
  const point = (sales, hour) => `${chartPadding.left + (hour / 23) * plotWidth},${chartPadding.top + plotHeight - (sales / maxSales) * plotHeight}`;
  const points = salesByHour.map(point).join(' ');
  const yLines = [0, .25, .5, .75, 1].map(ratio => { const y = chartPadding.top + plotHeight - ratio * plotHeight; return `<line x1="${chartPadding.left}" y1="${y}" x2="${chartWidth - chartPadding.right}" y2="${y}"/><line class="chart-tick" x1="${chartPadding.left - 7}" y1="${y}" x2="${chartPadding.left}" y2="${y}"/><text x="${chartPadding.left - 12}" y="${y + 5}" text-anchor="end">${money(maxSales * ratio)}</text>`; }).join('');
  const xLabels = salesByHour.map((_, hour) => hour % 2 === 0 ? `<line class="chart-tick" x1="${chartPadding.left + (hour / 23) * plotWidth}" y1="${chartPadding.top + plotHeight}" x2="${chartPadding.left + (hour / 23) * plotWidth}" y2="${chartPadding.top + plotHeight + 7}"/><text x="${chartPadding.left + (hour / 23) * plotWidth}" y="${chartHeight - 14}" text-anchor="middle">${String(hour).padStart(2, '0')}:00</text>` : '').join('');
  const dots = salesByHour.map((sales, hour) => `<circle cx="${point(sales, hour).split(',')[0]}" cy="${point(sales, hour).split(',')[1]}" r="${sales ? 3.5 : 2}" class="sales-point"><title>${String(hour).padStart(2, '0')}:00 — ${money(sales)}</title></circle>`).join('');
  $('#salesChart').innerHTML = `<svg width="100%" height="300" viewBox="0 0 ${chartWidth} ${chartHeight}" role="img" aria-label="Cumulative sales amount by time of day"><g class="chart-grid">${yLines}</g><line class="chart-axis" x1="${chartPadding.left}" y1="${chartPadding.top}" x2="${chartPadding.left}" y2="${chartPadding.top + plotHeight}"/><line class="chart-axis" x1="${chartPadding.left}" y1="${chartPadding.top + plotHeight}" x2="${chartWidth - chartPadding.right}" y2="${chartPadding.top + plotHeight}"/><polyline class="sales-line" points="${points}"/><g>${dots}</g>${xLabels}</svg>`;
  const itemSales = {};
  deliveredToday.forEach(order => order.items.forEach(item => { const amount = (Number(item.price) || 0) * (Number(item.quantity) || 0); itemSales[item.name] = (itemSales[item.name] || 0) + amount; }));
  const itemEntries = Object.entries(itemSales).sort((a, b) => b[1] - a[1]);
  const itemTotal = itemEntries.reduce((sum, [, amount]) => sum + amount, 0);
  const colors = ['#e95732', '#4c8059', '#e6a23c', '#6c63a8', '#3d91a6', '#bf5b93', '#77736e'];
  let offset = 0;
  const pieStops = itemEntries.map(([name, amount], index) => { const start = offset; offset += (amount / (itemTotal || 1)) * 100; return `${colors[index % colors.length]} ${start}% ${offset}%`; }).join(', ');
  $('#itemSalesPie').style.background = itemEntries.length ? `conic-gradient(${pieStops})` : '#e8dfd4';
  $('#itemSalesLegend').innerHTML = itemEntries.length ? itemEntries.map(([name, amount], index) => `<div class="legend-row"><i style="background:${colors[index % colors.length]}"></i><span>${escapeHtml(name)}</span><strong>${money(amount)}</strong></div>`).join('') : '<span class="analytics-empty">No item sales today.</span>';
  $('#completedOrdersHistory').innerHTML = completed.length ? completed.map(order => `<tr><td class="history-order-id">${escapeHtml(order.id)}</td><td>${escapeHtml(order.customer_name || order.user_name || 'Customer')}</td><td>${new Date(order.created_at * 1000).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'})}</td><td>${order.items.map(item => `${item.quantity}× ${escapeHtml(item.name)}`).join(' · ')}</td><td>${money(order.total)}</td><td><span class="history-status ${order.status === 'DELIVERED' ? 'delivered' : 'cancelled'}">${order.status === 'DELIVERED' ? 'Completed' : 'Cancelled'}</span></td></tr>`).join('') : '<tr><td colspan="6" class="history-empty">No completed orders yet.</td></tr>';
}
function renderMenu() { $('#menuList').innerHTML = dashboard.menu.length ? dashboard.menu.map(item => `<div class="menu-row"><span class="dish-icon">${item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt=""/>` : escapeHtml(item.emoji || '🍽️')}</span><div><div class="dish-name">${escapeHtml(item.name)} ${foodMark(item)}</div><div class="dish-price">${money(item.price)}</div></div><div class="dish-actions"><button class="availability ${item.available ? '' : 'off'}" data-availability="${item.id}">${item.available ? 'Available' : 'Hidden'}</button><button class="remove-item" title="Remove item" data-remove="${item.id}">×</button></div></div>`).join('') : '<div class="empty-state">No menu items yet. Add your first dish above.</div>'; document.querySelectorAll('[data-availability]').forEach(button => button.onclick = () => toggleItem(Number(button.dataset.availability))); document.querySelectorAll('[data-remove]').forEach(button => button.onclick = () => removeItem(Number(button.dataset.remove))); }
if (!$('#itemType')) $('#itemEmoji').insertAdjacentHTML('afterend', '<select id="itemType" aria-label="Food type"><option value="veg">Veg</option><option value="non-veg">Non-veg</option></select>');
$('#addForm').onsubmit = async event => { event.preventDefault(); try { await request(`/api/partner/restaurants/${selectedRestaurant}/menu`, {method:'POST',body:JSON.stringify({name:$('#itemName').value,price:$('#itemPrice').value,emoji:$('#itemEmoji').value || '🍽️',imageUrl:$('#itemImage').value,foodType:$('#itemType').value})}); $('#addForm').reset(); $('#itemType').value = 'veg'; $('#addForm').hidden = true; toast('New dish added'); await loadDashboard(); } catch (error) { toast(error.message); } };
configurePartnerRoute();
loadRestaurants().catch(error => toast(error.message));
const partnerLogoutButton = document.querySelector('#partnerLogout');
if (partnerLogoutButton) partnerLogoutButton.textContent = 'Logout';
