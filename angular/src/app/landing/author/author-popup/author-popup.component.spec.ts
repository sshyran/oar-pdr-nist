import { async, ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthorPopupComponent } from './author-popup.component';
import { FormsModule } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { SearchService } from '../../../shared/search-service/index';
// import { HttpClient, HttpHeaders } from '@angular/common/http'; 
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { ConfigModule } from '../../../config/config.module';
import { TransferState, StateKey } from '@angular/platform-browser';

describe('AuthorPopupComponent', () => {
  let component: AuthorPopupComponent;
  let fixture: ComponentFixture<AuthorPopupComponent>;
  let newAuthor = {
    "authors": [
      {
        "familyName": "Dow",
        "fn": "John Dow",
        "givenName": "John",
        "middleName": "",
        "affiliation": [
          {
            "@id": "",
            "title": "",
            "dept": "",
            "@type": [
              ""
            ]
          }
        ],
        "orcid": "",
        "isCollapsed": false,
        "fnLocked": false,
        "dataChanged": false
      }]
  };

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ AuthorPopupComponent ],
      imports: [FormsModule,        
        RouterTestingModule,
        HttpClientTestingModule,
        ConfigModule],
      schemas: [NO_ERRORS_SCHEMA],
      providers: [NgbActiveModal, SearchService, TransferState]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    let tempAuthors = {author: newAuthor};

    fixture = TestBed.createComponent(AuthorPopupComponent);
    component = fixture.componentInstance;
    component.inputValue = tempAuthors;
    component.title = 'author';
    fixture.detectChanges();
  });

  it('Should create', () => {
    expect(component).toBeTruthy();
  });

});
