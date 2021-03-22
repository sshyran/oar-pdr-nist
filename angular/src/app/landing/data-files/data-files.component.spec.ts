import { NO_ERRORS_SCHEMA } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { async, ComponentFixture, TestBed } from '@angular/core/testing';
import { DataFilesComponent } from './data-files.component';
import { FormsModule } from '@angular/forms';
import { CartService } from '../../datacart/cart.service';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { DownloadService } from '../../shared/download-service/download-service.service';
import { TestDataService } from '../../shared/testdata-service/testDataService';
import { AppConfig } from '../../config/config';
import { AngularEnvironmentConfigService } from '../../config/config.service';
import { TransferState } from '@angular/platform-browser';
import { GoogleAnalyticsService } from '../../shared/ga-service/google-analytics.service';
import { ToastrModule } from 'ngx-toastr';
import { TreeTableModule } from 'primeng/treetable';

describe('DataFilesComponent', () => {
  let component: DataFilesComponent;
  let fixture: ComponentFixture<DataFilesComponent>;
  let cfg: AppConfig;
  let plid: Object = "browser";
  let ts: TransferState = new TransferState();

  beforeEach(async(() => {
    cfg = (new AngularEnvironmentConfigService(plid, ts)).getConfig() as AppConfig;
    cfg.locations.pdrSearch = "https://goob.nist.gov/search";
    cfg.status = "Unit Testing";
    cfg.appVersion = "2.test";

    TestBed.configureTestingModule({
      declarations: [DataFilesComponent],
      imports: [FormsModule,
        RouterTestingModule,
        HttpClientTestingModule,
        TreeTableModule,
        ToastrModule.forRoot()],
      schemas: [NO_ERRORS_SCHEMA],
      providers: [
        CartService,
        DownloadService,
        TestDataService,
        GoogleAnalyticsService,
        DatePipe,
        { provide: AppConfig, useValue: cfg }]
    })
      .compileComponents();
  }));

  beforeEach(() => {
    let record: any = require('../../../assets/sampleRecord.json');
    fixture = TestBed.createComponent(DataFilesComponent);
    component = fixture.componentInstance;
    component.record = record;
    // component.distdownload = "/od/ds/zip?id=ark:/88434/mds0149s9z";
    // component.filescount = 8;
    component.metadata = false;
    // component.recordEditmode = false;
    component.inBrowser = true;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
    expect(component.files.length > 0).toBeTruthy();
    expect(component.fileCount).toBe(3);
    expect(component.downloadStatus).not.toBe("downloaded");
    expect(component.allInCart).toBeFalsy();
  });

  it('Should have title Data Access', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('h3').innerText).toEqual('Data Access');
  });

  it('Should have file tree table', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('th').length).toBeGreaterThan(0);
  });

  it('cartProcess() should be called', () => {
    let cmpel = fixture.nativeElement;
    let aels = cmpel.querySelectorAll(".icon-cart")[0];
    spyOn(component, 'toggleAllFilesInGlobalCart');
    aels.click();
    expect(component.toggleAllFilesInGlobalCart).toHaveBeenCalled();
  });
});
