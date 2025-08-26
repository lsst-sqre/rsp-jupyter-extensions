import { JupyterFrontEnd } from '@jupyterlab/application';
import { PageConfig } from '@jupyterlab/coreutils';
import { apiRequest, IJSONResponse } from './request';

// IEnvResponse encapsulates the environment variables we
// care about.  It's always a string-to-string mapping.
interface IEnvResponse {
  ABNORMAL_STARTUP?: string;
  ABNORMAL_STARTUP_ERRORCODE?: string;
  ABNORMAL_STARTUP_ERRNO?: string;
  ABNORMAL_STARTUP_STRERROR?: string;
  ABNORMAL_STARTUP_MESSAGE?: string;
  IMAGE_DESCRIPTION?: string;
  IMAGE_DIGEST?: string;
  JUPYTER_IMAGE_SPEC?: string;
  JUPYTERHUB_PUBLIC_URL?: string;
  EXTERNAL_INSTANCE_URL?: string;
  CPU_LIMIT?: string;
  MEM_LIMIT?: string;
  CONTAINER_SIZE?: string;
  RSP_SITE_TYPE?: string;
  DEBUG?: string;
}

export function getServerEnvironment(
  app: JupyterFrontEnd
): Promise<IEnvResponse> {
  const endpoint = PageConfig.getBaseUrl() + 'rubin/environment';
  const init = {
    method: 'GET'
  };
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;

  return apiRequest(endpoint, init, settings).then(env => {
    return env as IEnvResponse;
  });
}

export type { IJSONResponse };
export type { IEnvResponse };
