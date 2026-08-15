/**
 * Bound Apps Script for the hospital Google Sheet.
 * Run setupReleaseTrigger once after pasting this file.
 */
const CONFIG = {
  sheetId: '1gkHumsymX037G_PjioUIoAIpnUnOvTqoI4TgSHd7H6c',
  statusCell: 'E2',
  updatingValue: 'updating',
  releasedValue: 'released',
  dispatchCooldownMs: 60 * 1000,
  workflowFile: 'sync-hospitals.yml',
  workflowRef: 'main',
  repository: 'duancongdong/capcuudotquy',
};

/**
 * Run manually once. It removes this project's duplicate edit triggers, then
 * creates exactly one installable trigger for the release action.
 */
function setupReleaseTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === 'onEditReleasedStatus')
    .forEach(trigger => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger('onEditReleasedStatus')
    .forSpreadsheet(CONFIG.sheetId)
    .onEdit()
    .create();
}

function onEditReleasedStatus(event) {
  if (!event || !event.range) return;
  const editedRange = event.range;
  const sheet = editedRange.getSheet();

  // Do not run for bulk paste, whole-sheet updates, formatting, or edits to
  // other cells. Only a direct one-cell edit of E2 may publish data.
  if (sheet.getParent().getId() !== CONFIG.sheetId
    || editedRange.getNumRows() !== 1
    || editedRange.getNumColumns() !== 1
    || editedRange.getA1Notation() !== CONFIG.statusCell) return;

  const newValue = String(event.value || '').trim().toLowerCase();
  const oldValue = String(event.oldValue || '').trim().toLowerCase();
  if (oldValue !== CONFIG.updatingValue || newValue !== CONFIG.releasedValue) return;

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const lastDispatchAt = Number(properties.getProperty('LAST_SYNC_DISPATCH_UNIX_MS') || 0);
    if (Date.now() - lastDispatchAt < CONFIG.dispatchCooldownMs) return;

    const token = properties.getProperty('GITHUB_ACTIONS_TOKEN');
    if (!token) throw new Error('Thiếu Script Property GITHUB_ACTIONS_TOKEN');

    const sheetGid = sheet.getSheetId();
    const endpoint = `https://api.github.com/repos/${CONFIG.repository}/actions/workflows/${CONFIG.workflowFile}/dispatches`;
    const response = UrlFetchApp.fetch(endpoint, {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${token}`,
        'X-GitHub-Api-Version': '2022-11-28',
      },
      payload: JSON.stringify({
        ref: CONFIG.workflowRef,
        inputs: { sheet_id: CONFIG.sheetId, sheet_gid: String(sheetGid) },
      }),
    });

    if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
      throw new Error(`GitHub workflow dispatch lỗi ${response.getResponseCode()}: ${response.getContentText()}`);
    }
    properties.setProperty('LAST_SYNC_DISPATCH_AT', new Date().toISOString());
    properties.setProperty('LAST_SYNC_DISPATCH_UNIX_MS', String(Date.now()));
  } finally {
    lock.releaseLock();
  }
}
