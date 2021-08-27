import { NO_ERRORS_SCHEMA } from '@angular/core';
import { async, ComponentFixture, TestBed } from '@angular/core/testing';
import { CommonModule } from '@angular/common';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';

import { MetadataComponent } from './metadata.component';
import { MetadataModule } from './metadata.module';
import { AppConfig } from '../../config/config';
import { NerdmRes, NERDResource } from '../../nerdm/nerdm';
import { GoogleAnalyticsService } from '../../shared/ga-service/google-analytics.service';
import { config, testdata } from '../../../environments/environment';
import { By } from "@angular/platform-browser";

describe('MetadataComponent', () => {
    let component: MetadataComponent;
    let fixture: ComponentFixture<MetadataComponent>;
    let cfg : AppConfig = new AppConfig(config);
    let rec : NerdmRes = testdata['test1'];

    beforeEach(async(() => {
        TestBed.configureTestingModule({
            imports: [ MetadataModule ],
            providers: [
                { provide: AppConfig, useValue: cfg },
                GoogleAnalyticsService
            ]
        }).compileComponents();
    }));

    beforeEach(() => {
        fixture = TestBed.createComponent(MetadataComponent);
        component = fixture.componentInstance;
        component.record = rec;
        component.inBrowser = true;
        component.ngOnChanges({});
        fixture.detectChanges();
    });

    fit('should create', () => {
        component.mobileMode = false;
        expect(component).toBeTruthy();

        let cmpel = fixture.nativeElement;
        let jsonViewer = cmpel.querySelector("#json-viewer");
        expect(jsonViewer).toBeTruthy();

        //For nornal mode, there should be 4 expand buttons ("1", "2", "3", "View Full Tree")
        let jsonExpandButtons = fixture.debugElement.queryAll(By.css('li'));
        expect(jsonExpandButtons.length).toBe(4);

        //For mobile mode, there should be only 3 expand buttons ("1", "2", "Full Tree")
        component.mobileMode = true;
        fixture.detectChanges();
        jsonExpandButtons = fixture.debugElement.queryAll(By.css('li'));
        expect(jsonExpandButtons.length).toBe(3);

        let el = cmpel.querySelector("#more-info");
        expect(el).toBeTruthy();
        el = el.querySelector("a");
        expect(el).toBeTruthy();
        expect(el.textContent).toContain("NERDm documentation");
    });

    it('getDownloadURL()', () => {
        expect(component.getDownloadURL()).toEqual("https://data.nist.gov/rmm/records/?@id=ark:/88434/mds0000fbk");
    });
});
