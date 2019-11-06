export const environment = {
  production: true,
  RMMAPI: 'http://testdata.nist.gov/rmm/',
  SDPAPI:  'http://testdata.nist.gov/sdp/',
  PDRAPI:  'http://localhost:5555/#/id/',
  DISTAPI: 'https://localhost/od/ds/',
  METAPI:  'http://localhost/metaurl/',
  LANDING: 'http://testdata.nist.gov/rmm/'
};

import { LPSConfig } from '../app/config/config';

export const context = {
    production: true
};

export const config : LPSConfig = {
    locations: {
        orgHome:     "https://nist.gov/",
        portalBase:  "https://data.nist.gov/",
        pdrHome:     "https://data.nist.gov/pdr/",
        pdrSearch:   "https://data.nist.gov/sdp/"
    },
    customizationAPI: "https://data.nist.gov/customization/",
    mode:        "dev",
    status:      "Dev Version",
    appVersion:  "v1.1.0",
    production:  context.production
}
