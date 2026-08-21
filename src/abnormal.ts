import { JupyterFrontEnd } from '@jupyterlab/application';
import { PageConfig } from '@jupyterlab/coreutils';
import { showDialog, Dialog } from '@jupyterlab/apputils';
import { ITranslator, nullTranslator } from '@jupyterlab/translation';
import { INubladoConfigResponse } from './config';
import { LogLevels, logMessage } from './logger';
import { apiRequest } from './request';

export interface IAbnormalResponse {
  ABNORMAL_STARTUP?: string;
  ABNORMAL_STARTUP_ERRORCODE?: string;
  ABNORMAL_STARTUP_ERRNO?: string;
  ABNORMAL_STARTUP_STRERROR?: string;
  ABNORMAL_STARTUP_MESSAGE?: string;
  NB_HOME?: string;
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
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<void> {
  // Someday it would be nice to have a DialogBox class that understood
  // markdown.
  const trans = (translator || nullTranslator).load('jupyterlab');
  const options = {
    title: trans.__('Abnormal Lab Start'),
    body: getDialogBody(abnormal, translator),
    focusNodeSelector: 'input',
    buttons: [Dialog.warnButton({ label: trans.__('OK') })]
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

function getDialogBody(
  abnormal: IAbnormalResponse,
  translator: ITranslator | null
): string {
  const trans = (translator || nullTranslator).load('jupyterlab');
  let errno = -1;
  if (abnormal.ABNORMAL_STARTUP_ERRNO) {
    errno = parseInt(abnormal.ABNORMAL_STARTUP_ERRNO);
  }
  let errorcode = 'EUNKNOWN';
  if (abnormal.ABNORMAL_STARTUP_ERRORCODE) {
    errorcode = abnormal.ABNORMAL_STARTUP_ERRORCODE;
  }

  let strerror = trans.__('unknown error');
  if (abnormal.ABNORMAL_STARTUP_STRERROR) {
    strerror = abnormal.ABNORMAL_STARTUP_STRERROR;
  }
  let msg = '???';
  if (abnormal.ABNORMAL_STARTUP_MESSAGE) {
    msg = abnormal.ABNORMAL_STARTUP_MESSAGE;
  }
  let body = getSupplementalBody(errorcode, translator, abnormal.NB_HOME || '');
  body =
    body +
    '\n\n' +
    trans.__(
      'JupyterLab started in an abnormal state: Error # %1 (%2) [%3] "%4"',
      errno,
      errorcode,
      strerror,
      msg
    );
  return body;
}

function getSupplementalBody(
  errorcode: string,
  translator: ITranslator | null,
  homedir: string
): string {
  const trans = (translator || nullTranslator).load('jupyterlab');
  const no_trust =
    ' ' + trans.__('This Lab should not be trusted for work you want to keep.');
  const delete_something =
    ' ' +
    (homedir
      ? trans.__(
          'Try deleting unneeded .user_env directories and no-longer relevant large files in $NB_HOME (%1), then shut down and restart the Lab.',
          homedir
        )
      : trans.__(
          'Try deleting unneeded .user_env directories and no-longer relevant large files, then shut down and restart the Lab.'
        ));
  const no_storage =
    trans.__('You have run out of filesystem space.') + delete_something;
  const no_quota =
    trans.__('You have exceeded your filesystem quota.') + delete_something;
  const no_permission =
    trans.__(
      'You do not have permission to write. Ask your RSP site administrator to check ownership and permissions on your directories.'
    ) + no_trust;
  const no_idea =
    trans.__(
      'Please open an issue with your RSP site administrator with the error number, description, and message shown above.'
    ) + no_trust;
  const no_environment =
    trans.__(
      'You are missing environment variables necessary for RSP operation.'
    ) +
    ' ' +
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
