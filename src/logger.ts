import { INubladoConfigResponse } from './config';

enum LogLevels {
  DEBUG = 'debug',
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error'
}

export function logMessage(
  level: LogLevels,
  cfg: INubladoConfigResponse | null = null,
  message: string,
  ...optionalParams: any[]
) {
  if (level === LogLevels.DEBUG && cfg && cfg.debug) {
    console.log(message, ...optionalParams);
  } else if (level === LogLevels.INFO) {
    console.log(message, ...optionalParams);
  } else if (level === LogLevels.WARNING) {
    console.warn(message, ...optionalParams);
  } else if (level === LogLevels.ERROR) {
    console.error(message, ...optionalParams);
  }
}

export { LogLevels };
