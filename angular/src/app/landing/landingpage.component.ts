import { Component, OnInit, AfterViewInit,
         ElementRef, PLATFORM_ID, Inject, ViewEncapsulation } from '@angular/core';
import { ActivatedRoute, Router, NavigationEnd } from '@angular/router';
import { isPlatformBrowser } from '@angular/common';
import { Title } from '@angular/platform-browser';

import { AppConfig } from '../config/config';
import { MetadataService } from '../nerdm/nerdm.service';
import { EditStatusService } from './editcontrol/editstatus.service';
import { NerdmRes, NERDResource } from '../nerdm/nerdm';
import { IDNotFound } from '../errors/error';
import { MetadataUpdateService } from './editcontrol/metadataupdate.service';

/**
 * A component providing the complete display of landing page content associated with 
 * a resource identifier.  This content is handle in various sub-components.
 * 
 * Features include:
 * * an "identity" section, providing title, names, identifiers, and who is repsonsible
 * * description section, providing thd prose description/abstract, keywords, terms, ...
 * * a data access section, including a file listing (if files are availabe) and other links
 * * a references section
 * * tools and navigation section.
 *
 * This component sets the view encapsulation to None: this means that the style settings 
 * defined in landingpage.component.css apply globally, including to all the child components.
 */
@Component({
    selector: 'pdr-landing-page',
    templateUrl: './landingpage.component.html',
    styleUrls: ['./landingpage.component.css'],
    providers: [
        Title
    ],
    encapsulation:  ViewEncapsulation.None
})
export class LandingPageComponent implements OnInit, AfterViewInit {
    layoutCompact: boolean = true;
    layoutMode: string = 'horizontal';
    profileMode: string = 'inline';
    md: NerdmRes = null;       // the NERDm resource metadata
    reqId: string;             // the ID that was used to request this page
    inBrowser: boolean = false;
    citetext: string = null;
    citationVisible: boolean = false;
    editEnabled: boolean = false;
    citationDialogWith: number = 550; // Default width

    // this will be removed in next restructure
    showMetadata = false;

    /**
     * create the component.
     * @param route   the requested URL path to be fulfilled with this view
     * @param router  the router to use to reroute output, if necessary
     * @param titleSv the Title service (used to set the browser's title bar)
     * @param cfg     the app configuration data
     * @param mdserv  the MetadataService for gaining access to the NERDm metadata.
     * @param res     a CurrentResource object for sharing the metadata and requested 
     *                 ID with child components.
     */
    constructor(private route: ActivatedRoute,
                private router: Router,
                @Inject(PLATFORM_ID) private platformId: Object,
                public titleSv: Title,
                private cfg: AppConfig,
                private mdserv: MetadataService,
                private edstatsvc: EditStatusService,
                private mdupdsvc : MetadataUpdateService)
    {
        this.reqId = this.route.snapshot.paramMap.get('id');
        this.inBrowser = isPlatformBrowser(platformId);
        this.editEnabled = cfg.get('editEnabled', false) as boolean;
    }

    /**
     * initialize the component.  This is called early in the lifecycle of the component by 
     * the Angular rendering infrastructure.
     */
    ngOnInit() {
        console.log("initializing LandingPageComponent around id=" + this.reqId);
        // retreive the (unedited) metadata
        this.mdserv.getMetadata(this.reqId).subscribe(
            (data) => {
                // successful metadata request
                this.md = data;
                if (!this.md) {
                    // id not found; reroute
                    console.error("No data found for ID=" + this.reqId);
                    this.router.navigateByUrl("/not-found/" + this.reqId, { skipLocationChange: true });
                }
                else
                    // proceed with rendering of the component
                    this.useMetadata();
            },
            (err) => {
                console.error("Failed to retrieve metadata: " + err.toString());
                if (err instanceof IDNotFound)
                    this.router.navigateByUrl("not-found/" + this.reqId, { skipLocationChange: true });
                else
                    this.router.navigateByUrl("int-error/" + this.reqId, { skipLocationChange: true });
            }
        );

        // if editing is enabled, the editing can be triggered via a URL parameter.  This is done
        // in concert with the authentication process that can involve redirection to an authentication
        // server; on successful authentication, the server can redirect the browser back to this
        // landing page with editing turned on.  
        if (this.edstatsvc.editingEnabled()) {
            this.route.queryParamMap.subscribe(queryParams => {
                let param = queryParams.get("editmode")
                // console.log("editmode url param:", param);
                if (param) {
                    console.log("Returning from authentication redirection (editmode="+param+")");
                    // Need to pass reqID (resID) because the resID in editControlComponent
                    // has not been set yet and the startEditing function relies on it.
                    this.edstatsvc.startEditing(this.reqId);
                }
            })
        }
    }

    /**
     * apply housekeeping after view has been initialized
     */
    ngAfterViewInit() {
        this.useFragment();
        if (this.md && this.inBrowser) {
            window.history.replaceState({}, '', '/od/id/' + this.reqId);
        }
    }

    /**
     * make use of the metadata to initialize this component.  This is called asynchronously
     * from ngOnInit after the metadata has been successfully retrieved (and saved to this.md).
     * 
     * This method will:
     *  * set the page's title (as displayed in the browser title bar).
     */
    useMetadata(): void {
        // set the document title
        this.setDocumentTitle();
        this.mdupdsvc._setOriginalMetadata(this.md);
    }

    /**
     * set the document's title.  
     */
    setDocumentTitle(): void {
        let title = "PDR: ";
        if (this.md['abbrev']) title += this.md['abbrev'] + " - ";
        if (this.md['title'])
            title += this.md['title']
        else
            title += this.md['@id']
        this.titleSv.setTitle(title);
    }

    /**
     * return the current document title
     */
    getDocumentTitle(): string { return this.titleSv.getTitle(); }

    /**
     * apply the URL fragment by scrolling to the proper place in the document
     */
    public useFragment() {
        if (! this.inBrowser) return;

        this.router.events.subscribe(s => {
            if (s instanceof NavigationEnd) {
                const tree = this.router.parseUrl(this.router.url);
                let element = null;
                if (tree.fragment) {
                    element = document.querySelector("#" + tree.fragment);
                }
                else {
                    element = document.querySelector("body");
                    if (! element) 
                        console.warn("useFragment: failed to find document body!");
                }
                if (element) {
                    //element.scrollIntoView(); 
                    setTimeout(() => {
                        element.scrollIntoView({ behavior: "smooth", block: "start", inline: "nearest" });
                    }, 1);
                }
            }
        });
    }

    goToSection(sectionId: string) {
        this.showMetadata = (sectionId == "metadata");
        if (sectionId) 
            this.router.navigate(['/od/id/', this.reqId], { fragment: sectionId });
        else
            this.router.navigate(['/od/id/', this.reqId], { fragment: "" });
    }

    /**
     * display or hide citation information in a popup window.
     * @param yesno   whether to show (true) or hide (false)
     */
    showCitation(yesno : boolean) : void {
        this.citationVisible = yesno;
    }

    /**
     * toggle the visibility of the citation pop-up window
     */
    toggleCitation(size: string) : void { 
        if(size == 'small')
            this.citationDialogWith = 400;
        else
            this.citationDialogWith = 550;

        this.citationVisible = !this.citationVisible; 
    }

    /**
     * return text representing the recommended citation for this resource
     */
    getCitation() : string {
        if (! this.citetext) 
            this.citetext = (new NERDResource(this.md)).getCitation();
        return this.citetext;
    }

}
