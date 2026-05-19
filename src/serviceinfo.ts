import { JupyterFrontEnd } from '@jupyterlab/application';
import { PageConfig } from '@jupyterlab/coreutils';
import { apiRequest } from './request';

// IRSPServiceInfoResponse encapsulates the service info we need to know about.
export interface IRSPServiceInfoResponse {
  environment_name: string | null;
  datasets: { [key: string]: string };
  service: { [key: string]: string };
  ui: { [key: string]: string };
}

export async function getServiceInfo(
  app: JupyterFrontEnd
): Promise<IRSPServiceInfoResponse> {
  const endpoint = PageConfig.getBaseUrl() + 'rubin/serviceinfo';
  const init = {
    method: 'GET'
  };
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;

  const resp = await apiRequest(endpoint, init, settings);
  return resp as unknown as IRSPServiceInfoResponse;
}
