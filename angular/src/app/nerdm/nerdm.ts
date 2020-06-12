/**
 * Classes and interfaces to support the NERDm metadata infrastructure
 */
import { Injectable, InjectionToken } from '@angular/core';

import * as _ from 'lodash';

/**
 * a representation of a NERDm Component
 */
export interface NerdmComp {
    
    /**
     * the primary, local identifier for the resource
     */
    "@type" : string[];

    /**
     * the primary, local identifier for the resource
     */
    "@id"? : string;

    /**
     * the title of the component
     */
    title? : string;

    /**
     * the path to the component within a file hierarchy.  This is only applicable to 
     * DataFile and Subcollection components.
     */
    filepath? : string;

    /**
     * other parameters are expected
     */
    [propName: string]: any;
}

/**
 * a representation of a NERDm Resource 
 */
export interface NerdmRes {

    /**
     * the primary, local identifier for the resource
     */
    "@id" : string;

    /**
     * the title of the resource
     */
    title : string;

    /**
     * the list of components that are part of this resource
     */
    components? : NerdmComp[];

    /**
     * other parameters are expected
     */
    [propName: string]: any;
}

/**
 * a class interpreting a NerdmRes record.  This class wraps a NerdmRes object in an 
 * interface that provides functions that generate views on that information useful to 
 * displaying it.
 */
export class NERDResource {

    /**
     * wrap a NerdRes record (the data that describes a data resource)
     */
    constructor(public data : NerdmRes) { }

    /**
     * return the recommend text for citing this resource
     */
    getCitation() : string {
        if (this.data['citation'])
            return this.data.citation;

        let out = ""
        if (this.data['authors']) {
            for (let i = 0; i < this.data['authors'].length; i++) {
                let author = this.data['authors'][i];
                if (author.familyName !== null && author.familyName !== undefined)
                    out += author.familyName + ', ';
                if (author.givenName !== null && author.givenName !== undefined)
                    out += author.givenName;
                if (author.middleName !== null && author.middleName !== undefined)
                    out += ' ' + author.middleName;
                if (i != this.data['authors'].length - 1)
                    out += ', ';
            }
        }
        else if (this.data['contactPoint'] && this.data['contactPoint']['fn']) {
            out += this.data['contactPoint']['fn'];
        }
        else if (this.data['publisher'] && this.data['publisher']['name']) {
            out += this.data['publisher']['name'];
        }
        else {
            out += "National Institute of Standards and Technology";
        }

        let date = this.data['issued'];
        if (! date)
            date = this.data['modified'];
        if (date)
            out += ' (' + date.split('-')[0] + ')';

        if (this.data['title'])
            out += ', ' + this.data['title'];
        if (this.data['publisher'] && this.data['publisher']['name']) 
            out += ', ' + this.data['publisher']['name'];

        if (this.data['doi']) {
            let doi = this.data['doi'];
            if (doi.startsWith("doi:"))
                doi = "https://doi.org/" + doi.split(':').slice(1).join(':')
            out += ', ' + doi;
        }
        else if (this.data['landingPage']) {
            out += ', ' + this.data['landingPage'];
        }

        date = new Date();
        out += " (Accessed " + date.getFullYear() + '-'
        let n = date.getMonth() + 1;
        n = (n < 10) ? "0" + n.toString() : n.toString();
        out += n + '-';
        n = date.getDate();
        n = (n < 10) ? "0" + n.toString() : n.toString();
        out += n + ')';
        
        return out
    }

    static _isstring(v : any, i?, a?) : boolean {
        return typeof v === 'string' || v instanceof String;
    }
    static _stripns(t : string, i?, a?) : string {
        return t.substr(t.indexOf(':')+1);
    }
    static _striptypes(cmp : {}) : string[] {
        if (! cmp['@type']) return [];

        let out = cmp['@type']
        if (this._isstring(out)) out = [ out ];
        if (! Array.isArray(out)) return []

        return out.filter(this._isstring).map(this._stripns).sort()
    }
    static _typesintersect(obj : {}, types : string[]) : boolean {
        // we will assume that types is strictly an ordered array of strings
        let ctypes : string[] = this._striptypes(obj).sort();

        for(var c of ctypes) {
            for(var t of types) {
                if (t == c) return true;  // found a matching type!
                if (t > c) break;
            }
        }
        return false;
    }

    /**
     * return true if there is an intersection between a given set of types
     * and the values in the "@type" property of a given object
     * @param obj    an object with the "@type" property; false will be returned 
     *               if the property does not exist or if it is not of type string 
     *               or array.
     * @param types  a string or an array of string type labels.  Any prepended 
     *               namespace prefixes will be ignored.  
     */
    static objectMatchesTypes(obj : {}, types : string|string[]) : boolean {
        if (this._isstring(types)) types = [types as string]
        if (! Array.isArray(types)) return false;
        types = types.filter(this._isstring).map(this._stripns).sort();

        return this._typesintersect(obj, types);
    }

    /**
     * return an array of the component objects that match any of the given @type labels.
     * The labels should not include namespace qualifiers
     */
    getComponentsByType(types : string|string[]) : any[] {
        if (! this.data['components'] || !Array.isArray(this.data['components']))
            return [];

        if (NERDResource._isstring(types)) types = [types as string]
        if (! Array.isArray(types)) return [];
        types = types.filter(NERDResource._isstring).map(NERDResource._stripns).sort();

        return this.data['components'].filter((c,i?,a?) => {
            return NERDResource._typesintersect(c, types as string[]);
        });
    }

    /**
     * return the number resource components that match any of the given @type labels.  
     * The labels should not include namespace qualifiers
     */
    countComponentsByType(types : string|string[]) {
        return this.getComponentsByType(types).length;
    }

    /**
     * return the components that should appear in the file listing display
     */
    getFileListComponents() {
        let listable = ["DataFile", "Subcollection", "ChecksumFile"];
        let hidden = ["Hidden"];
        return this.getComponentsByType(listable)
            .filter((c) => { return ! NERDResource.objectMatchesTypes(c, hidden); });
    }

    /**
     * return the number of components that should appear in the file listing display
     */
    countFileListComponents() {
        return this.getFileListComponents().length;
    }
}

/**
 * a container for transmitting metadata between the server and the browser
 * versions of the app.  
 */
@Injectable()
export class MetadataTransfer {
    private store : {} = {};

    /**
     * return the metadata saved with the given label
     */
    get(label : string) : {} | undefined {
        return this.store[label] as {};
    }

    /**
     * save the metadata with the given label
     */
    set(label : string, data : {}) : void {
        this.store[label] = data;
    }

    /**
     * return true if metadata with the given label has been 
     * saved to this cache yet.
     */
    isSet(label : string) : boolean {
        return this.store.hasOwnProperty(label);
    }

    /**
     * return an array of the labels that metadata have been saved under
     */
    labels() : string[] {
        return Object.keys(this.store);
    }

    /**
     * serialize into JSON and return the metadata with the given label
     * An empty string is returned if no metadata with the label has been
     * saved yet. 
     */
    serialize(label : string) : string {
        if (! this.isSet(label))
            return "";
        return JSON.stringify(this.store[label], null, 2);
    }
}

