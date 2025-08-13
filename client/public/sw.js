self.addEventListener('push', e => {
  const data = e.data?.json() || {};
  e.waitUntil(
    self.registration.showNotification(data.title || 'AgentLocator', {
      body: data.body,
      data,
      actions: [
        { action: 'call', title: 'התקשר' },
        { action: 'wa', title: 'פתח WhatsApp' },
        { action: 'snooze_15', title: 'נודניק 15ד׳' }
      ]
    })
  );
});