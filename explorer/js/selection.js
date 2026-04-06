var $pm, $pmid, $dname, $lastEditId;
const dsm = 'div[data-sm]';

function loadSMode() {
  $dname = dialogName();
  const savedId = $dname && sessionStorage.getItem('pmid:' + $dname);
  $pm = $(savedId ? '#' + savedId : window.location.hash || dsm).first();
  selectMsg($pm, { centered: true });
  $pm.length ? $pm.focus() : ed().focus();
}

function dialogName() { return new URLSearchParams(window.location.search).get('name'); }

function ed() { return window.editor; }

$(document).on('monaco:editorReady', () => {
  if (window.location.pathname !== '/dialog_') return;
  if (dialogName() !== $dname) loadSMode();
});

const noEditAnim = [
  { outlineColor: "oklch(57.7% 0.245 27.325)" }, { transform: "translateX(0)" },
  { transform: "translateX(5px)" }, { transform: "translateX(-5px)" },
  { transform: "translateX(0)" }, { outlineColor: "transparent" }]

function checkCanEdit(event) {
  // Check can edit $pm -> editor id_ === $pm.id OR editor has no text
  selectMsg($(event.target.closest('.editable'))); // Update $pm from event, so mouse-click events work correctly
  const idMatch = $('#id_').val() === $pm.attr('id');
  if ($('#submit_btn').is(':disabled')) return; // No websocket -> Cancel request
  if (!(ed().getValue() || idMatch)) return enterEditMode();
  event.preventDefault(); // Cancel edit request
  idMatch ? ed().focus() : $pm[0].animate(noEditAnim, { duration: 200, iterations: 1 });
}

function enterEditMode() {
  const prevEdit = $('[data-editing]');
  if (prevEdit && prevEdit.length) {
    prevEdit.attr('data-editing', false);
    $lastEditId = prevEdit[0].id;
  }
  if ($pm.length) {
    $pm.attr('data-editing', true);
    $lastEditId = $pm[0].id;
  }
}
function exitEditMode() { $pm.attr('data-editing', false) }

function _post(ep, payload = {}) {
  payload.dlg_name = $('#dlg_name').val();
  if (typeof payload.id_ !== 'string') payload.id_ = $pm.attr('id') || null;
  Object.assign(payload, { ids: selectedMsgIds() || null });
  htmx.ajax('POST', '/' + ep + '_', { values: payload, swap: 'none' });
}

function selectedMsgs() { return $('[data-sm="primary"], [data-sm="secondary"]') }
function selectedMsgIds() { return [...selectedMsgs()].map(el => el.id).join(',') }

function selectMsg(msg, opts = {}) {
  const { centered = false, scroll = true, multi = false } = opts;
  if (!msg.length) return false;
  const all = $(dsm);
  const [i1, i2] = [all.index($pm), all.index(msg)].sort((a, b) => a - b);
  const isNonConsec = i1 !== -1 && i2 - i1 > 1;
  if (multi && isNonConsec) { all.slice(i1, i2 + 1).attr('data-sm', 'secondary'); }
  else if ($pm && $pm.length) {
    $pm.attr('data-sm', multi && msg.attr('data-sm') === 'unselected' ? 'secondary' : 'unselected');
    if (!multi) $('[data-sm="secondary"]').attr('data-sm', 'unselected');
  }
  msg.attr('data-sm', 'primary');
  $pm = msg;
  $pmid = $pm.attr('id');
  if ($pmid && $dname) sessionStorage.setItem('pmid:' + $dname, $pmid);
  if (msg.is(':hidden')) _post('uncollapse_msg', {});
  if (scroll) requestAnimationFrame(() => msg[0].scrollIntoView({ block: centered ? 'center' : 'nearest' }));
  return true;
}

// Check function for outside-editor `Escape` keypresses (to exit edit mode)
function checkCanEscape() { return $("[data-editing=true]")?.length && !$(".uk-modal")?.length && !isAnyTextBoxActive(); }

// Used to check no input/textarea is focused before processing keybindings for selection mode
function isAnyTextBoxActive() { return document.activeElement?.matches('input,textarea'); }

// Ensure $dname is reset when navigating away from a dialog
$(document).on('htmx:beforeHistorySave', () => $dname = null);

function run_msg(cmd) { _post('add_runq', { cmd }); }
function upsert_msg(cmd) {
  _post('upsert_msg', {
    id_: $('#id_').val() || '', msg_type: $('#msg_type').val(), content: ed().getValue(),
    is_input: $('#is_input').val(), cmd
  });
}
function msg_clipboard(cmd) { _post('msg_clipboard', { cmd }); }
function msg_paste(after) { _post('msg_paste', { after }); }
function msg_undo() { _post('msg_undo', {}); }
function clipboardFeedback() {
  selectedMsgs().each((_, el) => { el.animate([{ opacity: 0.5 }, { opacity: 1 }], { duration: 200, iterations: 1 }) });
}

// Collapse/expand behavior (explained for collapse; expand is the opposite:
// if $pm is an expanded header then collapse it
// - or jump to the parent header (if $pm isn't a header)
// - or jump to the start of the file if there's no parent header
function headerLevel(el) { return Number(el.attr('data-sm-level')) || 9; }
function findHeader(start, direction, fallback) {
  let lvl = headerLevel(start), p = start;
  while ((p = p[direction]('[data-sm-header]')).length && headerLevel(p) > lvl);
  return p.length ? p : fallback;
}

function collapseHeading(multi) {
  if ($pm.attr('data-sm-header') === 'expanded') _post('toggle_header_collapse', { id_: $pm.attr('id') });
  else selectMsg(findHeader($pm, 'prevMatch', $('.editable').first()), { multi });
}

function expandHeading(multi) {
  if ($pm.attr('data-sm-header') === 'collapsed') _post('toggle_header_collapse', { id_: $pm.attr('id') });
  else selectMsg(findHeader($pm, 'nextMatch', $('.editable').last()), { multi });
}

function primaryMod(e) { return (/Mac|iPhone|iPad/.test(navigator.platform || '')) ? e.metaKey : e.ctrlKey; }

function closeFind() {
  $('#find-box').addClass('hidden');
  $('#find-box')[0].reset();
  htmx.trigger('#find-box', 'submit');
  // Uncollapse selected message after find closes
  if ($pmid) _post('uncollapse_msg');
}

const clickPost = (path, last = false) => $pm.find(`[hx-post="/${path}"]`)[last ? 'last' : 'first']().click();
const clickId = (id) => document.getElementById(id).click();
const nav = dir => $pm[dir + 'Match'](dsm);

// message events
function isKey(event, letter, shiftKey) { return event.key.toLowerCase() === letter && event.shiftKey === shiftKey; }

$(document).on('keydown', (event) => {
  if (isAnyTextBoxActive() || $('#full_editor').has(event.target).length || !dialogName() || event.target.id === 'dlg-name') return;
  let key = event.key || event.detail.key;
  let code = event.code || event.detail.code;
  if (!event.shiftKey && primaryMod(event)) {
    switch (key) {
      case '/': _post('toggle_comment', {}); break;
    }
  } else if (event.shiftKey && primaryMod(event)) {
    let handled = true;
    switch (key) {
      case 'j': _post('set_mtyp', { mtyp: 'code' }); break;
      case 'k': _post('set_mtyp', { mtyp: 'note' }); break;
      case 'l': _post('set_mtyp', { mtyp: 'prompt' }); break;
      case ';': _post('set_mtyp', { mtyp: 'raw' }); break;
      case '.': _post('continue_prompt'); break;
      case 'ArrowUp': clickPost('shift_up_'); break;
      case 'ArrowDown': clickPost('shift_down_'); break;
      default: handled = false;
    }
    if (handled) event.preventDefault();
  } else if (!event.metaKey && !event.altKey && !event.ctrlKey) {
    if ((key === 'ArrowDown' || code === "KeyJ") && selectMsg(nav('next'), { multi: event.shiftKey })) { }
    else if ((key === 'ArrowUp' || code === "KeyK") && selectMsg(nav('prev'), { multi: event.shiftKey })) { }
    else if (key === 'Home' && selectMsg($(dsm).first(), { multi: event.shiftKey })) { }
    else if (key === 'End' && selectMsg($(dsm).last(), { multi: event.shiftKey })) { }
    else if (key === 'ArrowLeft') collapseHeading(event.shiftKey);
    else if (key === 'ArrowRight') expandHeading(event.shiftKey);
    else if (key === 'Backspace') _post('clear_out');
    else if (isKey(event, 'a', false)) clickPost('add_above_');
    else if (isKey(event, 'a', true)) clickPost('run_above_');
    else if (isKey(event, 'b', false)) clickPost('add_below_');
    else if (isKey(event, 'b', true)) clickPost('run_below_');
    else if (isKey(event, 'c', true)) clickId('checkpoint');
    else if (isKey(event, 'd', false)) clickId('duplicate');
    else if (isKey(event, 'd', true)) clickPost(`rm_msg_?msid=${$pm.attr('id')}`);
    else if (isKey(event, 'e', false)) clickPost('toggle_export_');
    else if (isKey(event, 'f', false)) $('#find-box').removeClass('hidden').find('#search').focus();
    else if (isKey(event, 'f', true)) closeFind();
    else if (isKey(event, 'h', false)) clickPost('toggle_skip_');
    else if (isKey(event, 'i', false)) clickPost('collapse_');
    else if (isKey(event, 'o', false)) clickPost('collapse_', true);
    else if (isKey(event, 'i', true)) _post('clamp', { is_input: 1 });
    else if (isKey(event, 'o', true)) _post('clamp', { is_input: 0 });
    else if (isKey(event, 'l', false)) _post('chat_messages', { refresh_ws: true });
    else if (isKey(event, 'm', true)) _post('merge_msg');
    else if (isKey(event, 'm', false)) clickPost('copy_code_');
    else if (isKey(event, 'n', false)) clickPost('editor_', true);
    else if (isKey(event, 'p', false)) clickPost('toggle_pin_');
    else if (isKey(event, 'q', false)) clickPost('dup_msg_');
    else if (isKey(event, 'r', false)) clickId('run-all');
    else if (isKey(event, 'r', true)) clickId('reset');
    else if (isKey(event, 'w', false)) clickPost('split_code_');
    else if (isKey(event, 's', false)) _post('save_dlg');
    else if (isKey(event, 's', true)) clickId('stop');
    else if (isKey(event, 't', false)) $pm.find('a[href^="/show_card_"]').get(0)?.click();
    else if (isKey(event, 't', true)) $('#terminal').get(0)?.click();
    else if (isKey(event, 'y', false)) $pm.find('a[href^="/show_card_"]').get(-1)?.click();
    else if (key === '_') clickPost('split_msg_');
    else if (key === '?') clickId('info-btn');
    else if (event.shiftKey && event.code?.startsWith('Digit')) _post('bookmark', { n: Number(event.code.slice(-1)) });
    else if ('123456789'.includes(key)) _post('goto_bookmark', { n: Number(key) });
    else if (key === '0') { selectMsg($(`#${$lastEditId}`)); }
    else if (isKey(event, 'c', false)) { msg_clipboard('copy'); clipboardFeedback(); }
    else if (isKey(event, 'x', false)) msg_clipboard('cut');
    else if (isKey(event, 'v', false)) msg_paste(true);
    else if (isKey(event, 'v', true)) msg_paste(false);
    else if (isKey(event, 'z', false)) msg_undo();
    else if (key === ',') clickPost('copy_msg_');
    else if (key === '.') clickPost('copy_msg_', true);
    else if (key === '/') ed().focus();
    else if (key === 'Enter') {
      if (event.shiftKey) {
        if ($pm.attr('data-sm-header') === 'collapsed') _post('toggle_header_collapse', { id_: $pm.attr('id') });
        run_msg('shift-run');
      }
      else clickPost('editor_');
    }
    else return;
    event.preventDefault();
  }
  if (primaryMod(event) && event.shiftKey && key === 'Enter') {
      run_msg('run');
      _post('continue_prompt');
  }
  else if (event.metaKey && key === 'Enter') run_msg('run');
  else if (event.altKey && key === 'Enter') run_msg('alt-run');
  else return;
  event.preventDefault();
});

/*
After we execute an operation (e.g. delete a message) we need to determine the next `$pm` and whether we should be in edit or selection mode. While we could do this client-side, it becomes trickier for more complex commands like cut/paste, expanding/collapsing headers. However, it is relatively straightforward to determine the correct `$pm` server-side. We pass next $pm value to the client via a htmx response header.

Specifically, our message related endpoints such as `upsert_msg_`, `add_above_`, `add_below_` etc. return htmx response headers that trigger a custom event `smode:afterSettle`. This event includes the `id` of the new `$pm` as well as the `cmd` that was run.
*/

$(document).on('smode:afterSettle', ({ detail: { id, cmd } }) => {
  // We save the id because our messages are passed through a websocket and might not be in the DOM when this code runs.
  // By saving $pmid we can run `selectMsg` when `htmx:wsAfterMessage` fires and the message is in the DOM.
  if (cmd === 'chat-messages' && !id) { id = $pm.attr('id') }
  $pmid = id;
  if ($pmid) {
    let el = $(`div[id='${$pmid}']`).first();
    if (el.length) selectMsg(el);
  }
  if (!$pmid && !$(dsm).first().length && !isAnyTextBoxActive()) {
    $pm = $();
    ed().focus();
  }
  else if (cmd === 'add' || cmd.includes('alt-run')) {
    enterEditMode();
    ed().focus();
  }
  else {
    exitEditMode();
    if (cmd.endsWith('shift-run')) selectMsg($pm.nextMatch(dsm));
    if (cmd.startsWith('upsert')) $lastEditId = $pmid;
    if (ed().hasWidgetFocus()) document.activeElement.blur();
  }
});

// The websocket swap removes the original element `$pm` pointed at, so we rerun `selectMsg` on the swapped-in msg.
// Also now updates `dynamicon` based on loading state.
htmx.on('htmx:wsAfterMessage', ({ detail }) => {
  // EXPERIMENTAL: Don't scroll to new message unless already selected
  let m = detail.message;
  // search the root and child elements for the `data-sm` attribute.
  let $m = $(m).filter('[data-sm]').add($(m).find('[data-sm]'));
  if ($pmid && m.includes($pmid)) {
    // calling `selectMsg` overrides $pm's `data-editing` attribute so we need to save it and then reapply it.
    let editing = $pm?.attr('data-editing');
    selectMsg($('#' + $pmid));
    if (editing) enterEditMode()
  }
  else if (!$pm?.length && $m.length) selectMsg($m.first(), { scroll: false, centered: true });
  let favi = htmx.find('[rel="icon"]');
  favi.href = htmx.find('.animate-spin') ? '/assets/loadicon.ico' : '/assets/favicon.ico';
});
