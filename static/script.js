const form = document.getElementById('chat-form');
const queryField = document.getElementById('query');
const conversation = document.getElementById('conversation');

function createWorkflowStatus() {
  const stepPanel = document.createElement('div');
  stepPanel.className = 'message bot';

  const stepBox = document.createElement('div');
  stepBox.className = 'status-box workflow-panel';

  const heading = document.createElement('strong');
  heading.textContent = 'Working';

  const list = document.createElement('ul');
  list.className = 'workflow-steps';

  stepBox.appendChild(heading);
  stepBox.appendChild(list);
  stepPanel.appendChild(stepBox);
  conversation.appendChild(stepPanel);
  conversation.scrollTop = conversation.scrollHeight;
  return { heading, list };
}

function appendWorkflowStep(workflow, step) {
  const previous = workflow.list.lastElementChild;
  if (previous) {
    previous.classList.remove('is-active');
    previous.classList.add('is-complete');
  }

  const item = document.createElement('li');
  item.className = 'is-active';
  item.textContent = String(step).trim();
  workflow.list.appendChild(item);
  workflow.heading.textContent = 'Working';
  conversation.scrollTop = conversation.scrollHeight;
}

function finishWorkflow(workflow, title) {
  workflow.heading.textContent = title;
  const active = workflow.list.querySelector('.is-active');
  if (active) {
    active.classList.remove('is-active');
    active.classList.add('is-complete');
  }
}

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function applyInlineMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  return html;
}

function renderMarkdown(markdown) {
  const lines = markdown.replace(/\r/g, '').split('\n');
  let html = '';
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    if (line.trim().startsWith('|') && i + 1 < lines.length && lines[i + 1].trim().startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(lines[i].trim());
        i += 1;
      }

      const tableRows = rows.map((row) => row.split('|').slice(1, -1).map((cell) => cell.trim()));
      if (tableRows.length >= 2) {
        const headers = tableRows[0];
        const bodyRows = tableRows.slice(2);

        html += '<table><thead><tr>' + headers.map((header) => `<th>${applyInlineMarkdown(header)}</th>`).join('') + '</tr></thead><tbody>';
        bodyRows.forEach((row) => {
          html += '<tr>' + row.map((cell) => `<td>${applyInlineMarkdown(cell)}</td>`).join('') + '</tr>';
        });
        html += '</tbody></table>';
        continue;
      }
    }

    if (/^###\s+/.test(line.trim())) {
      html += `<h3>${applyInlineMarkdown(line.trim().replace(/^###\s+/, ''))}</h3>`;
      i += 1;
      continue;
    }

    if (/^##\s+/.test(line.trim())) {
      html += `<h2>${applyInlineMarkdown(line.trim().replace(/^##\s+/, ''))}</h2>`;
      i += 1;
      continue;
    }

    if (/^#\s+/.test(line.trim())) {
      html += `<h1>${applyInlineMarkdown(line.trim().replace(/^#\s+/, ''))}</h1>`;
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(line.trim())) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(applyInlineMarkdown(lines[i].trim().replace(/^[-*]\s+/, '')));
        i += 1;
      }
      html += '<ul>' + items.map((item) => `<li>${item}</li>`).join('') + '</ul>';
      continue;
    }

    if (/^\d+\.\s+/.test(line.trim())) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(applyInlineMarkdown(lines[i].trim().replace(/^\d+\.\s+/, '')));
        i += 1;
      }
      html += '<ol>' + items.map((item) => `<li>${item}</li>`).join('') + '</ol>';
      continue;
    }

    const paragraphLines = [];
    while (i < lines.length && lines[i].trim() && !lines[i].trim().startsWith('|') && !/^#{1,6}\s+/.test(lines[i].trim()) && !/^[-*]\s+/.test(lines[i].trim()) && !/^\d+\.\s+/.test(lines[i].trim())) {
      paragraphLines.push(lines[i].trim());
      i += 1;
    }
    if (paragraphLines.length) {
      html += `<p>${paragraphLines.map((part) => applyInlineMarkdown(part)).join('<br>')}</p>`;
      continue;
    }

    i += 1;
  }

  return html || '<p>No content</p>';
}

function addMessage(role, text) {
  const row = document.createElement('div');
  row.className = `message ${role}`;

  const bubble = document.createElement(role === 'user' ? 'p' : 'div');
  bubble.className = 'message-content';

  if (role === 'user') {
    bubble.textContent = text;
  } else {
    bubble.innerHTML = renderMarkdown(text);
  }

  row.appendChild(bubble);
  conversation.appendChild(row);
  conversation.scrollTop = conversation.scrollHeight;
}

queryField.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const query = queryField.value.trim();
  if (!query) return;

  addMessage('user', query);
  queryField.value = '';
  queryField.disabled = true;
  form.querySelector('button').disabled = true;

  const workflow = createWorkflowStatus();
  appendWorkflowStep(workflow, 'Connecting to the assistant...');

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    if (!response.ok) {
      const data = await response.json();
      finishWorkflow(workflow, 'Request failed');
      addMessage('bot', data.error || 'Something went wrong.');
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let answer = '';

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === 'step') {
          appendWorkflowStep(workflow, event.step);
        } else if (event.type === 'answer') {
          answer = event.answer;
        } else if (event.type === 'error') {
          throw new Error(event.error);
        }
      }

      if (done) break;
    }

    if (buffer.trim()) {
      const event = JSON.parse(buffer);
      if (event.type === 'answer') answer = event.answer;
      if (event.type === 'error') throw new Error(event.error);
      if (event.type === 'step') appendWorkflowStep(workflow, event.step);
    }

    finishWorkflow(workflow, 'Complete');
    addMessage('bot', answer || 'No response received.');
  } catch (error) {
    finishWorkflow(workflow, 'Request failed');
    addMessage('bot', `Request failed: ${error.message}`);
  } finally {
    queryField.disabled = false;
    form.querySelector('button').disabled = false;
    queryField.focus();
  }
});
