import { Injectable, ViewChild, PLATFORM_ID, APP_ID, Inject, Directive } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { makeStateKey, TransferState } from '@angular/platform-browser';
// import 'rxjs/add/operator/map';
// import 'rxjs/add/operator/catch';
// import 'rxjs/add/observable/throw';
import { catchError, map } from 'rxjs/operators';
import 'rxjs';
import { AppConfig } from '../../config/config';
import * as _ from 'lodash-es';
import { tap } from 'rxjs/operators';
import { isPlatformServer } from '@angular/common';
import { MessageBarComponent } from '../../frame/messagebar.component';
import { BehaviorSubject } from 'rxjs';

export const SEARCH_SERVICE = 'SEARCH_SERVICE';
/**
 * This class provides the Search service with methods to search for records from tha rmm.
 */
@Directive()
@Injectable()
export class SearchService {

    private landingBackend: string = "";
    private rmmBackend: string;
    editEnabled: any;
    portalBase: string = "https://data.nist.gov";

    currentPage = new BehaviorSubject<number>(1);
    totalItems = new BehaviorSubject<number>(1);

    @ViewChild(MessageBarComponent, { static: true })
    private msgbar: MessageBarComponent;

    /**
     * Creates a new SearchService with the injected Http.
     * @param {Http} http - The injected Http.
     * @constructor
     */
    constructor(
        private http: HttpClient, 
        private transferState: TransferState,
        @Inject(PLATFORM_ID) private platformId: Object,
        private cfg: AppConfig) {
        this.landingBackend = cfg.get("mdAPI", "/unconfigured");
        this.portalBase = cfg.get("locations.portalBase", "data.nist.gov");

        if (this.landingBackend == "/unconfigured")
            throw new Error("Metadata service endpoint not configured!");

        this.rmmBackend = cfg.get("locations.mdService", "/unconfigured");
        if (this.rmmBackend == "/unconfigured")
            throw new Error("mdService endpoint not configured!");
    }

    /**
     * Create  a local service to test
     */
    testdata(): Observable<any> {
        //"http://localhost:4200/assets/sampledata.json"
        console.log("Test service here:" + this.landingBackend);
        return this.http.get(this.landingBackend);
    }
    
    searchById(searchValue: string, browserside: boolean = false) {
        var backend: string = this.landingBackend;

        if(browserside){
            backend = this.rmmBackend;
        }

        if (_.includes(backend, 'rmm') && _.includes(searchValue, 'ark'))
            backend += 'records?@id=';
        else if (_.includes(backend, 'rmm')) {
            if(!_.includes(backend, 'records'))
                backend += 'records/';
        }

        // console.log("Querying backend:", backend + searchValue);
        return this.http.get(backend + searchValue, { headers: new HttpHeaders({ timeout: '${10000}' }) });
    }

    getAllRecords(): Observable<any> {
        // if (_.includes(this.landingBackend, 'rmm'))
        return this.http.get(this.rmmBackend + 'records?');
    }

    getData(recordid: string): Observable<any> {
        const recordid_KEY = makeStateKey<string>('record-' + recordid);

        if (this.transferState.hasKey(recordid_KEY)) {
            console.log("extracting data id=" + recordid + " embedded in web page");
            const record = this.transferState.get<any>(recordid_KEY, null);
            // this.transferState.remove(recordid_KEY);
            return of(record);
        }
        else {
            console.warn("record data not found in transfer state");
            return this.searchById(recordid)
                .pipe(
                    tap(record => {
                        if (isPlatformServer(this.platformId)) {
                            this.transferState.set(recordid_KEY, record);
                        }
                    }),
                    catchError((err: Response, caught: Observable<any[]>) => {
                        // console.log(err);
                        if (err !== undefined) {
                            console.error("Failed to retrieve data for id=" + recordid + "; error status=" + err.status);
                            if ("message" in err) console.error("Reason: " + (<any>err).message);
                            if ("url" in err) console.error("URL used: " + (<any>err).url);
    
                            let msg = "Failed to retrieve data for id=" + recordid;
                            this.msgbar.error(msg);
    
                            if (err.status == 0) {
                                console.warn("Possible causes: Unable to trust site cert, CORS restrictions, ...");
                                return Observable.throw('Unknown error requesting data for id=' + recordid);
                            }
                        }
                        return Observable.throw(caught);
                    })
                )
        }
    }

    /**
     * Returns an Observable for the HTTP GET request for the JSON resource.
     * @return {string[]} The Observable for the HTTP request.
     */
    searchPhrase(): Observable<any> {
        let url: string;

        url = this.portalBase + "rmm/records?isPartOf.proxyFor=ark:/88434/mds9911";

        console.log('search url', url);
        return this.http.get(url);
    }

    /**
     * Watch current page
     */
        watchCurrentPage(): Observable<any> {
        return this.currentPage.asObservable();
    }
    
    /**
     * Set curent page
     * @param page 
     */
    setCurrentPage(page: number) {
        this.currentPage.next(page);
    }


    /**
     * Watch total items (search result)
     */
     watchTotalItems(): Observable<any>{
        return this.totalItems.asObservable();
    }

    /**
     * Set total items (search result)
     * @param page 
     */
    setTotalItems(totalItems: number) {
        this.totalItems.next(totalItems);
    }

}


