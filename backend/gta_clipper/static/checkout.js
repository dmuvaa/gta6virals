/* Opens Paddle's checkout for the clicked plan. Paddle handles payment, tax and receipts;
   our webhook upgrades the account once the subscription is active. */
(() => {
  let cfg = null;
  async function setup() {
    if (cfg) return cfg;
    const r = await fetch('/billing/checkout-config');
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || 'Checkout is unavailable right now.');
    if (d.environment !== 'production') Paddle.Environment.set('sandbox');
    Paddle.Initialize({ token: d.token });
    return (cfg = d);
  }
  document.addEventListener('click', async e => {
    const b = e.target.closest('.js-upgrade'); if (!b || b.disabled) return;
    b.disabled = true;
    try {
      const c = await setup();
      Paddle.Checkout.open({
        items: [{ priceId: c.prices[b.dataset.plan], quantity: 1 }],
        customer: { email: c.email },
        customData: { user_id: c.user_id },
        settings: { successUrl: c.success_url, displayMode: 'overlay', theme: 'dark' },
      });
    } catch (err) { alert(err.message); }
    finally { b.disabled = false; }
  });
})();
