import { NgModule }     from '@angular/core';
import { CommonModule } from '@angular/common';
import { DatePipe }     from '@angular/common';
import { ButtonModule } from 'primeng/button';

import { NerdmModule } from '../nerdm/nerdm.module';
import { LandingPageComponent } from './landingpage.component';
import { LandingModule } from '../landing/landing.module';
import { MetadataUpdateService } from './editcontrol/metadataupdate.service';
import { EditControlModule } from './editcontrol/editcontrol.module';
import { ToolsModule } from './tools/tools.module';
import { CitationModule } from './citation/citation.module';

/**
 * A module supporting the complete display of landing page content associated with 
 * a resource identifier
 */
@NgModule({
    imports: [
        CommonModule,
        ButtonModule,
        NerdmModule,    // provider for MetadataService (which depends on AppConfig)
        LandingModule,
        EditControlModule,
        ToolsModule,
        CitationModule
    ],
    declarations: [
        LandingPageComponent,
    ],
    providers: [
        MetadataUpdateService, DatePipe
    ],
    exports: [
        LandingPageComponent
    ]
})
export class LandingPageModule { }

export { LandingPageComponent };
    
