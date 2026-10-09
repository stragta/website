(function () {
  'use strict';

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    textarea.remove();
    if (!copied) throw new Error('No se pudo copiar');
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.copy').forEach(function (button) {
      const defaultLabel = button.getAttribute('aria-label') || 'Copiar este prompt';
      button.setAttribute('aria-label', defaultLabel);
      button.addEventListener('click', async function () {
        const target = button.closest('.prompt')?.querySelector('code');
        const text = target ? (target.innerText || target.textContent || '') : '';
        const original = button.textContent;
        try {
          await copyText(text);
          button.textContent = 'Copiado';
          button.setAttribute('aria-label', 'Contenido copiado');
        } catch (error) {
          button.textContent = 'Selecciona el texto';
        }
        window.setTimeout(function () {
          button.textContent = original;
          button.setAttribute('aria-label', defaultLabel);
        }, 1600);
      });
    });
  });
}());
