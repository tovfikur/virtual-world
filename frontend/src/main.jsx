import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/index.css';

// Optional: silence non-error console output to avoid noisy logs
if (import.meta.env.VITE_SILENCE_LOGS === 'true') {
  ['log', 'info', 'debug', 'warn'].forEach((method) => {
    if (typeof console[method] === 'function') {
      console[method] = () => {};
    }
  });
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
