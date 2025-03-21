import { showDialog, Dialog } from '@jupyterlab/apputils';
import { IEnvResponse } from './environment';
import { LogLevels, logMessage } from './logger';

export async function abnormalDialog(env: IEnvResponse): Promise<void> {
  const options = {
    title: 'Degraded Mode',
    body: getDialogBody(env),
    focusNodeSelector: 'input',
    buttons: [Dialog.warnButton({ label: 'OK' })]
  };
  try {
    const result = await showDialog(options);
    if (!result) {
      logMessage(LogLevels.DEBUG, env, 'No result from queryDialog');
      return;
    }
    logMessage(LogLevels.DEBUG, env, `Result from queryDialog: ${result}`);
    if (!result.value) {
      logMessage(LogLevels.DEBUG, env, 'No result.value from queryDialog');
      return;
    }
    if (!result.button) {
      logMessage(LogLevels.DEBUG, env, 'No result.button from queryDialog');
      return;
    }
    return;
  } catch (error) {
    console.error(`Error showing abnormal startup dialog ${error}`);
    throw new Error(`Failed to show abnormal startup dialog: ${error}`);
  }
}

function getDialogBody(env: IEnvResponse): string {
  let errno = -1;
  if (env.ABNORMAL_STARTUP_ERRNO) {
    errno = parseInt(env.ABNORMAL_STARTUP_ERRNO);
  }
  let strerror = 'unknown error';
  if (env.ABNORMAL_STARTUP_STRERROR) {
    strerror = env.ABNORMAL_STARTUP_STRERROR;
  }
  let msg = '???';
  if (env.ABNORMAL_STARTUP_MESSAGE) {
    msg = env.ABNORMAL_STARTUP_MESSAGE;
  }
  let body = `JupyterLab is running in degraded mode: error # ${errno} [${strerror}] "${msg}"`;
  body = body + '\n\n' + getSupplementalBody(errno);
  return body;
}

function getSupplementalBody(errno: number): string {
  const no_trust = ' This Lab should not be trusted for work you want to keep.';
  const no_storage =
    'You have run out of storage space. Try deleting unneeded .user_env directories and no-longer relevant large files, then shut down and restart the Lab.';
  const no_permission =
    'You do not have permission to write. Ask your RSP site administrator to check ownership and permissions on your directories.' +
    no_trust;
  const no_idea =
    'Please open an issue with your RSP site administrator with the error number, description, and message shown above.' +
    no_trust;
  const no_environment =
    'You are missing environment variables necessary for RSP operation. ' +
    no_idea;
  switch (errno) {
    case 13:
      return no_permission;
      break;
    case 28:
      return no_storage;
      break;
    case 30:
      return no_permission;
      break;
    case 104:
      return no_environment;
      break;
    case 122:
      return no_storage;
      break;
    default:
      return no_idea;
      break;
  }
}
