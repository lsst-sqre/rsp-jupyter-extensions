import { ServerConnection } from '@jupyterlab/services';

// IJSONResponse is just "whatever we got, as JSON"
export interface IJSONResponse {
  value: {
    [key: string]: any;
  };
}

export function apiRequest(
  url: string,
  init: RequestInit,
  settings: ServerConnection.ISettings
): Promise<IJSONResponse> {
  // Fake out URL check in makeRequest
  return ServerConnection.makeRequest(url, init, settings).then(response => {
    if (response.status !== 200) {
      return response.json().then(data => {
        throw new ServerConnection.ResponseError(response, data.message);
      });
    }
    return response.json();
  });
}
