import { Component, Input, Output, OnChanges, ViewChild, EventEmitter } from '@angular/core';

import { MenuItem } from 'primeng/api';
import { Menu } from 'primeng/menu';

import { AppConfig } from '../../config/config';
import { NerdmRes } from '../../nerdm/nerdm';

/**
 * A component for displaying access to landing page tools in a menu.
 * 
 * Items include:
 * * links to the different sections of the landing page
 * * links to view or export metadata
 * * information about usage (like Citation information in a pop-up)
 * * links for searching for similar resources
 */
@Component({
    selector: 'tools-menu',
    template: `
<p-menu #tmenu [ngClass]="{'rightMenuStyle': !isPopup, 'rightMenuStylePop': isPopup}" 
               [popup]="isPopup" [model]="items"></p-menu>
`,
    styleUrls: ['./toolmenu.component.css']
})
export class ToolMenuComponent implements OnChanges {

    // the resource record metadata that the tool menu data is drawn from
    @Input() record : NerdmRes|null = null;

    // true if this menu should appear as a popup
    @Input() isPopup : boolean = false;

    // signal for triggering display of the citation information
    @Output() toggle_citation = new EventEmitter<boolean>();

    // signal for scrolling to a section within the page
    @Output() scroll = new EventEmitter<string>();

    // reference to the child menu (needed to toggle display when isPopup = true)
    @ViewChild('tmenu')
    private menu : Menu;

    // the menu item configuration
    items: MenuItem[] = [];

    /**
     * create the component.
     * @param cfg   the app configuration data
     */
    constructor(private cfg : AppConfig) {  }

    /**
     * toggle the appearance of a popup menu
     */
    togglePopup(click) {
        if (this.isPopup)
            this.menu.toggle(click);
    }

    /**
     * update the component state when the record metadata is updated
     */
    ngOnChanges() {
        if (this.record) 
            this.updateMenu();
    }

    /**
     * configure the menu using data from the record metadata
     */
    updateMenu() {
        var mitems : MenuItem[] = [];
        var subitems : MenuItem[] = [];

        let mdapi = this.cfg.get("locations.mdService", "/unconfigured");
        if (mdapi.slice(-1) != '/') mdapi += '/';
        if (mdapi.search("/rmm/") < 0)
            mdapi += this.record['ediid'];
        else
            mdapi += "records?@id=" + this.record['@id'];

        // Go To...
        // top of the page
        subitems.push(
            this.createMenuItem("Top", "faa faa-arrow-circle-right",
                                (event) => { this.goToSection(null); }, null)
        );

        // Go To...
        subitems.push(
            this.createMenuItem("Description", "faa faa-arrow-circle-right",
                                (event) => { this.goToSection('description'); }, null)
        );

        // is it possible to not have a data access section?
        subitems.push(
            this.createMenuItem("Data Access", "faa faa-arrow-circle-right",
                                (event) => { this.goToSection('dataAccess'); }, null)
        );
        
        if (this.record['references'])
            subitems.push(
                this.createMenuItem("References", "faa faa-arrow-circle-right ",
                                    (event) => { this.goToSection('reference'); }, null)
            );
        mitems.push({ label: 'Go To...', items: subitems });

        // Record Details
        subitems = [
            this.createMenuItem("View Metadata", "faa faa-bars",
                                (event) => { this.goToSection('metadata'); },null),
            this.createMenuItem("Export JSON", "faa faa-file-o", null, mdapi)
        ];
        mitems.push({ label: "Record Details", items: subitems });

        // Use
        subitems = [
            this.createMenuItem('Citation', "faa faa-angle-double-right",
                                (event) => { this.toggleCitation(); }, null),
            this.createMenuItem("Fair Use Statement", "faa faa-external-link", null,
                                this.record['license'])
        ];
        mitems.push({ label: "Use", items: subitems });

        // Find
        let searchbase = this.cfg.get("locations.pdrSearch","/sdp/")
        if (searchbase.slice(-1) != '/') searchbase += "/"
        let authlist = "";
        if (this.record['authors']) {
            for (let a of this.record['authors']) {
                if (a['familyName'])
                    authlist += ","+a.familyName
            }
            if (authlist.length > 0) authlist = authlist.slice(1);
        }
        subitems = [
            this.createMenuItem("Similar Resources", "faa faa-external-link", null,
                                searchbase + "#/search?q=" + this.record['keyword'] +
                                "&key=&queryAdvSearch=yes"),
            this.createMenuItem('Resources by Authors', "faa faa-external-link", null,
                                searchbase + "#/search?q=authors.familyName=" + authlist +
                                "&key=&queryAdvSearch=yes")
        ];
        mitems.push({ label: "Find", items: subitems });

        this.items = mitems;
    }

    /**
     * create an entry for a menu
     * @param label     the label that should appear on the menu entry
     * @param icon      the class labels that define the icon to display next to the menu label
     * @param command   a function that should be executed when the menu item is selected.
     *                    The function should take a single argument representing the selection
     *                    event object
     * @param url       a URL that should be navigated to when the menu item is selected.
     */
    createMenuItem(label: string, icon: string, command: any, url: string) {
        let item : MenuItem = {
            label: label,
            icon: icon
        };
        if (command)
            item.command = command;
        if (url) {
            item.url = url;
            item.target = "_blank";
        }

        return item;
    }

    /**
     * switch the display of the Citation information:  if it is currently showing,
     * it should be hidden; if it is not visible, it should be shown.  This method
     * is trigger by clicking on the "Citation" link in the menu; clicking 
     * alternatively both shows and hides the display.
     *
     * The LandingPageComponent handles the actual display of the information
     * (currently implemented as a pop-up).  
     */
    toggleCitation() {
        this.toggle_citation.emit(true);
    }
    
    /**
     * scroll to the specified section of the landing page
     */
    goToSection(sectname : string) {
        if (sectname) 
            console.info("scrolling to #"+sectname+"...");
        else
            console.info("scrolling to top of document");
        this.scroll.emit(sectname);
    }
}
