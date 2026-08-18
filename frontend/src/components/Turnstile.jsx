import { useEffect, useRef } from 'react';

const SCRIPT_ID = 'cloudflare-turnstile-script';

export default function Turnstile({ siteKey, onToken }) {
  const container = useRef(null);

  useEffect(() => {
    if (!siteKey) return undefined;
    let widgetId;
    let active = true;
    const render = () => {
      if (!active || !container.current || !window.turnstile) return;
      widgetId = window.turnstile.render(container.current, {
        sitekey: siteKey,
        callback: onToken,
        'expired-callback': () => onToken(''),
        'error-callback': () => onToken(''),
      });
    };
    const prior = document.getElementById(SCRIPT_ID);
    if (window.turnstile) render();
    else if (prior) prior.addEventListener('load', render, { once: true });
    else {
      const script = document.createElement('script');
      script.id = SCRIPT_ID;
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      script.addEventListener('load', render, { once: true });
      document.head.appendChild(script);
    }
    return () => {
      active = false;
      if (widgetId !== undefined && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [onToken, siteKey]);

  return <div ref={container} className="turnstile-widget" aria-label="人机验证" />;
}
