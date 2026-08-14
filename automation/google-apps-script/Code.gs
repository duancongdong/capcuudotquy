/**
 * Bound Apps Script for the hospital Google Sheet.
 * Install an on-edit trigger for onEditReleasedStatus once.
 */
const CONFIG = {
  sheetId: '1gkHumsymX037G_PjioUIoAIpnUnOvTqoI4TgSHd7H6c',
  statusCell: 'E2',
  releasedValue: 'released',
  workflowFile: 'sync-hospitals.yml',
  workflowRef: 'main',
  repository: 'duancongdong/capcuudotquy',
};

function onEditReleasedStatus(event) {
  if (!event || !event.range) return;
  const editedRange = event.range;
  const statusRange = editedRange.getSheet().getRange(CONFIG.statusCell);
  const coversStatusCell = statusRange.getRow() >= editedRange.getRow()
    && statusRange.getRow() <= editedRange.getLastRow()
    && statusRange.getColumn() >= editedRange.getColumn()
    && statusRange.getColumn() <= editedRange.getLastColumn();
  if (!coversStatusCell) return;
  if (String(statusRange.getDisplayValue()).trim().toLowerCase() !== CONFIG.releasedValue) return;

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const token = properties.getProperty('GITHUB_ACTIONS_TOKEN');
    if (!token) throw new Error('Thiếu Script Property GITHUB_ACTIONS_TOKEN');

    const sheetGid = editedRange.getSheet().getSheetId();
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
  } finally {
    lock.releaseLock();
  }
}
