const currentAuthToken = () => localStorage.getItem('tastekart-auth-token') || '';
if (!currentAuthToken()) window.location.replace('/login');
document.querySelector('#profileButton').onclick = () => { window.location.href = currentAuthToken() ? '/profile' : '/login'; };
document.querySelector('#checkoutButton').onclick = () => { if (!currentAuthToken()) return window.location.href = '/login'; checkout(); };
