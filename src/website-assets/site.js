'use strict';
const form = document.querySelector('#contact-form');
if (form) {
  const topic = new URLSearchParams(location.search).get('thema');
  if (topic === 'rail') form.elements.topic.value = 'Rail Software';
  if (topic === 'musik') form.elements.topic.value = 'KI-Musik';
  const status = document.querySelector('#form-status');
  const button = document.querySelector('#send-button');
  // Static previews never send personal data to the production host.
  const configuredHost = location.origin === 'https://ctl-software.io-goerlitz.eu';
  const availability = document.querySelector('#form-availability');
  let ready = false;
  button.disabled = true;
  availability.textContent = configuredHost ? 'Verfügbarkeit des Formularversands wird geprüft …' : 'Vorschau: Der Formularversand ist hier nicht aktiv. Bitte verwenden Sie die oben angegebene E-Mail-Adresse oder Telefonnummer.';
  if (configuredHost) {
    fetch('/website-contact', {headers: {'Accept': 'application/json'}, cache: 'no-store'})
      .then(async response => {
        const data = await response.json();
        ready = response.ok && data.available === true;
        button.disabled = !ready;
        availability.textContent = ready ? 'Ihre Anfrage wird an Oliver Müller gesendet.' : 'Der Formularversand ist noch nicht eingerichtet. Bitte kontaktieren Sie mich per E-Mail oder Telefon.';
      })
      .catch(() => { availability.textContent = 'Der Formularversand ist derzeit nicht erreichbar. Bitte kontaktieren Sie mich per E-Mail oder Telefon.'; });
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!ready || !form.reportValidity()) return;
    button.disabled = true;
    status.textContent = 'Ihre Anfrage wird gesendet …';
    try {
      const response = await fetch('/website-contact', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: JSON.stringify(Object.fromEntries(new FormData(form)))
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Der Versand ist fehlgeschlagen. Bitte versuchen Sie es später oder kontaktieren Sie mich per E-Mail.');
      status.textContent = data.message;
      form.reset();
    } catch (error) {
      status.textContent = error instanceof SyntaxError || error instanceof TypeError ? 'Keine Versandbestätigung erhalten. Bitte prüfen Sie die Verbindung oder kontaktieren Sie mich per E-Mail.' : error.message;
    } finally { button.disabled = false; }
  });
}
