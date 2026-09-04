import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
// Les éléments personnalisés doivent être enregistrés avant le premier rendu.
import './material';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
