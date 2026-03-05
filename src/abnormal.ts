import { JupyterFrontEnd } from '@jupyterlab/application';
import { showDialog, Dialog } from '@jupyterlab/apputils';
import { PageConfig } from '@jupyterlab/coreutils';
import { apiRequest } from './request';

import { INubladoConfigResponse } from './config';
import { LogLevels, logMessage } from './logger';

export interface IAbnormalResponse {
  ABNORMAL_STARTUP?: string;
  ABNORMAL_STARTUP_ERRORCODE?: string;
  ABNORMAL_STARTUP_ERRNO?: string;
  ABNORMAL_STARTUP_STRERROR?: string;
  ABNORMAL_STARTUP_MESSAGE?: string;
}

export async function getAbnormalStartup(
  app: JupyterFrontEnd
): Promise<IAbnormalResponse> {
  const endpoint = PageConfig.getBaseUrl() + 'rubin/abnormal';
  const init = {
    method: 'GET'
  };
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;

  const resp = await apiRequest(endpoint, init, settings);
  return resp as IAbnormalResponse;
}

export async function abnormalDialog(
  abnormal: IAbnormalResponse,
  cfg: INubladoConfigResponse
): Promise<void> {
  const options = {
    title: 'Abnormal Lab Start',
    body: getDialogBody(abnormal),
    focusNodeSelector: 'input',
    buttons: [Dialog.warnButton({ label: 'OK' })]
  };
  try {
    const result = await showDialog(options);
    if (!result) {
      logMessage(LogLevels.DEBUG, cfg, 'No result from queryDialog');
      return;
    }
    logMessage(LogLevels.DEBUG, cfg, `Result from queryDialog: ${result}`);
    if (!result.value) {
      logMessage(LogLevels.DEBUG, cfg, 'No result.value from queryDialog');
      return;
    }
    if (!result.button) {
      logMessage(LogLevels.DEBUG, cfg, 'No result.button from queryDialog');
      return;
    }
    return;
  } catch (error) {
    console.error(`Error showing abnormal startup dialog ${error}`);
    throw new Error(`Failed to show abnormal startup dialog: ${error}`);
  }
}

function getDialogBody(abnormal: IAbnormalResponse): string {
  let errno = -1;
  if (abnormal.ABNORMAL_STARTUP_ERRNO) {
    errno = parseInt(abnormal.ABNORMAL_STARTUP_ERRNO);
  }
  let errorcode = 'EUNKNOWN';
  if (abnormal.ABNORMAL_STARTUP_ERRORCODE) {
    errorcode = abnormal.ABNORMAL_STARTUP_ERRORCODE;
  }

  let strerror = 'unknown error';
  if (abnormal.ABNORMAL_STARTUP_STRERROR) {
    strerror = abnormal.ABNORMAL_STARTUP_STRERROR;
  }
  let msg = '???';
  if (abnormal.ABNORMAL_STARTUP_MESSAGE) {
    msg = abnormal.ABNORMAL_STARTUP_MESSAGE;
  }
  let body = getSupplementalBody(errorcode);
  body =
    body +
    '\n\n' +
    `JupyterLab started in an abnormal state: error # ${errno} (${errorcode}) [${strerror}] "${msg}"`;
  return body;
}

function getSupplementalBody(errorcode: string): string {
  const no_trust = ' This Lab should not be trusted for work you want to keep.';
  const delete_something =
    ' Try deleting unneeded .user_env directories and no-longer relevant large files, then shut down and restart the Lab.';
  const no_storage = 'You have run out of filesystem space.' + delete_something;
  const no_quota =
    'You have exceeded your filesystem quota.' + delete_something;
  const no_permission =
    'You do not have permission to write. Ask your RSP site administrator to check ownership and permissions on your directories.' +
    no_trust;
  const no_idea =
    'Please open an issue with your RSP site administrator with the error number, description, and message shown above.' +
    no_trust;
  const no_environment =
    'You are missing environment variables necessary for RSP operation. ' +
    no_idea;
  switch (errorcode) {
    case 'EACCES':
      return no_permission;
    case 'ENOSPC':
      return no_storage;
    case 'EROFS':
      return no_permission;
    case 'EDQUOT':
      return no_quota;
    case 'EBADENV':
      return no_environment;
    default:
      return no_idea;
  }
}
