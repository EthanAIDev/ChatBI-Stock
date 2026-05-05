import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';
import 'highlight.js/styles/github-dark.css';
import 'katex/dist/katex.min.css';
import 'streamdown/styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
