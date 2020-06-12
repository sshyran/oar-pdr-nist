/***
 * A typescript interface describing what a product can contain.
 *
 * ( not to be confused by traditional oop interfaces, even if the goals are the same)
 *
 **/
export interface ZipData {
    fileName: any;
    downloadProgress: any;
    downloadStatus: any;
    downloadInstance: any;
    bundle: any;
    downloadUrl: any;
    downloadErrorMessage: any;
    bundleSize: number;
    downloadTime: number;
  }