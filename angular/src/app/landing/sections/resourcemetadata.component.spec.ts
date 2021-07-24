import { async, ComponentFixture, TestBed, ComponentFixtureAutoDetect } from '@angular/core/testing';

import { ResourceMetadataComponent } from './resourcemetadata.component';
import { SectionsModule } from './sections.module';

import { AppConfig } from '../../config/config';
import { NerdmRes, NerdmComp } from '../../nerdm/nerdm';
import { GoogleAnalyticsService } from '../../shared/ga-service/google-analytics.service';

import { config, testdata } from '../../../environments/environment';

describe('ResourceMetadataComponent', () => {
    let component: ResourceMetadataComponent;
    let fixture: ComponentFixture<ResourceMetadataComponent>;
    let cfg : AppConfig = new AppConfig(config);
    let rec : NerdmRes = testdata['test1'];

    let makeComp = function() {
        TestBed.configureTestingModule({
            imports: [ SectionsModule ],
            declarations: [  ],
            providers: [
                { provide: AppConfig, useValue: cfg },
                GoogleAnalyticsService
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(ResourceMetadataComponent);
        component = fixture.componentInstance;
    }

    beforeEach(async(() => {
        makeComp();
        component.inBrowser = true;
        component.record = JSON.parse(JSON.stringify(rec));
        component.ngOnChanges({});
        fixture.detectChanges();
    }));

    it('should initialize', () => {
        expect(component).toBeTruthy();
        let cmpel = fixture.nativeElement;
        expect(cmpel.querySelector("#metadata")).toBeTruthy();

        // has a section heading
        let el = cmpel.querySelector("h3");
        expect(el).toBeTruthy();
        expect(el.textContent).toContain("Metadata");
        el = cmpel.querySelector("legend");
        expect(el).toBeTruthy();
        expect(el.textContent).toContain("NERDm");
    });

});