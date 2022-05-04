import { Component, OnChanges, Input, ViewChild } from '@angular/core';

import { AppConfig } from '../../config/config';
import { NerdmRes, NERDResource } from '../../nerdm/nerdm';
import { VersionComponent } from '../version/version.component';
import { GoogleAnalyticsService } from '../../shared/ga-service/google-analytics.service';
import { EditStatusService } from '../../landing/editcontrol/editstatus.service';
import { LandingConstants } from '../../landing/constants';

/**
 * a component that lays out the "identity" section of a landing page
 */
@Component({
    selector:      'pdr-resource-id',
    templateUrl:   './resourceidentity.component.html',
    styleUrls:   [
        './resourceidentity.component.css', '../landing.component.css'
    ]
})
export class ResourceIdentityComponent implements OnChanges {

    recordType: string = "";
    doiUrl: string = null;
    showHomePageLink: boolean = true;
    primaryRefs: any[] = [];
    editMode: string;
    EDIT_MODES: any;
    isPartOf: string = "";

    // passed in by the parent component:
    @Input() record: NerdmRes = null;
    @Input() inBrowser: boolean = false;

    /**
     * create an instance of the Identity section
     */
    constructor(private cfg: AppConfig,
                public editstatsvc: EditStatusService,
                private gaService: GoogleAnalyticsService)
    { }

    ngOnInit(): void {
        this.EDIT_MODES = LandingConstants.editModes;

        if(this.record['isPartOf'] != undefined) {
            this.isPartOf = "Part of " + this.record['isPartOf'][0].title 
        }

        // Watch current edit mode set by edit controls
        this.editstatsvc.watchEditMode((editMode) => {
            this.editMode = editMode;
        });
    }

    /**
     * Decide if currently in view only mode
     */
    get inViewMode() {
        return this.editMode == this.EDIT_MODES.VIEWONLY_MODE;
    }

    ngOnChanges() {
        if (this.recordLoaded())
            this.useMetadata();  // initialize internal component data based on metadata
    }

    recordLoaded() {
        return this.record && ! (Object.keys(this.record).length === 0);
    }

    /**
     * initial this component's internal data used to drive the display based on the 
     * input resource metadata
     */
    useMetadata(): void {
        this.showHomePageLink = this.isExternalHomePage(this.record['landingPage']);
        this.recordType = (new NERDResource(this.record)).resourceLabel();

        if (this.record['doi'] !== undefined && this.record['doi'] !== "")
            this.doiUrl = "https://doi.org/" + this.record['doi'].substring(4);

        this.primaryRefs = (new NERDResource(this.record)).getPrimaryReferences();
        for (let ref of this.primaryRefs) {
            if (! ref['label'])
                ref['label'] = ref['title'] || ref['citation'] || ref['location']
        }
    }    

    /**
     * return true if the given URL does not appear to be a PDR-generated home page URL.
     * Note that if the input URL is not a string, false is returned.  
     */
    public isExternalHomePage(url : string) : boolean {
        if (! url)
            return false;
        let pdrhomeurl = /^https?:\/\/(\w+)(\.\w+)*\/od\/id\//
        return ((url.match(pdrhomeurl)) ? false : true);
    }

    /**
     * Google Analytics track event
     * @param url - URL that user visit
     * @param event - action event
     * @param title - action title
     */
    googleAnalytics(url: string, event, title) {
        this.gaService.gaTrackEvent('homepage', event, title, url);
    }

    /*
     * uncomment this as needed for debugging purposes
     *
    @ViewChild(VersionComponent)
    versionCmp : VersionComponent;
     */

}
