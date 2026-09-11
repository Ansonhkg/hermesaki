import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import typescript from 'highlight.js/lib/languages/typescript';
import json from 'highlight.js/lib/languages/json';
import http from 'highlight.js/lib/languages/http';
hljs.registerLanguage('bash',bash);hljs.registerLanguage('typescript',typescript);hljs.registerLanguage('json',json);hljs.registerLanguage('http',http);
export default hljs;
