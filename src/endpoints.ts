import { JupyterFrontEnd } from '@jupyterlab/application';
import { PageConfig } from '@jupyterlab/coreutils';
import { apiRequest } from './request';

// IRSPEndpointsResponse encapsulates the endpoints we need to know about.
export interface IRSPEndpointsResponse {
  environment_name: string;
  datasets: { [key: string]: string };
  service: { [key: string]: string };
  ui: { [key: string]: string };
}

export async function getEndpoints(
  app: JupyterFrontEnd
): Promise<IRSPEndpointsResponse> {
  const endpoint = PageConfig.getBaseUrl() + 'rubin/endpoints';
  const init = {
    method: 'GET'
  };
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;

  const resp = await apiRequest(endpoint, init, settings);
  return resp as unknown as IRSPEndpointsResponse;
}
