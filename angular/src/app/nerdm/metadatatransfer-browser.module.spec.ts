import * as mdt from './metadatatransfer-browser.module';
import * as smdt from './metadatatransfer-server.module';
import * as nrdsv from './nerdm.service';
import { MetadataTransfer } from './nerdm';

describe('initBrowserMetadataTransfer', function() {

    let doc : Document;
    let mdtrx : MetadataTransfer;
    let data1 : {} = { title: "All about me!" };
    let data2 : {} = { "@context": [ ],  title: "All about me!" };

    beforeEach(() => {
        doc = new Document();
        doc = doc.implementation.createHTMLDocument();
        mdtrx = null;
    });

    it('extract single entry', function() {
        let child = doc.createElement("script");
        child.setAttribute("type", "application/json");
        child.setAttribute("id", "goober");
        child.textContent = JSON.stringify(data1);
        doc.body.appendChild(child);
        doc.body.appendChild(doc.createElement("p"));

        mdtrx = mdt.initBrowserMetadataTransfer(doc);
        expect(mdtrx.get("goober")).toEqual(data1);
        expect(mdtrx.labels().length).toBe(1);
    });

    it('extract multiple entries', function() {
        let child = doc.createElement("script");
        child.setAttribute("type", "application/json");
        child.setAttribute("id", "goober");
        child.textContent = JSON.stringify(data1);
        doc.body.appendChild(child);
        
        doc.body.appendChild(doc.createElement("p"));

        child = doc.createElement("script");
        child.setAttribute("type", "application/ld+json");
        child.setAttribute("id", "gomer");
        child.textContent = JSON.stringify(data2);
        doc.body.appendChild(child);

        doc.body.appendChild(doc.createElement("p"));

        child = doc.createElement("script");
        child.setAttribute("type", "application/json");
        child.setAttribute("id", "myapp-state");
        child.textContent = JSON.stringify({ config: {} });
        doc.body.appendChild(child);

        mdtrx = mdt.initBrowserMetadataTransfer(doc);
        expect(mdtrx.get("goober")).toEqual(data1);
        expect(mdtrx.get("gomer")).toEqual(data2);
        expect(mdtrx.labels().length).toBe(2);
    });

    it('no entries', function() {
        doc.body.appendChild(doc.createElement("p"));

        mdtrx = mdt.initBrowserMetadataTransfer(doc);
        expect(mdtrx.labels().length).toBe(0);
        expect(mdtrx.get("goober")).toBeUndefined();
    });
});

describe('Test MetadataTransfer round trip', function() {
    let doc : Document;
    let mdtrx : MetadataTransfer;
    let data1 : {} = { title: "All about me!" };
    let data2 : {} = { "@context": [ ],  title: "All about me!" };

    beforeEach(() => {
        doc = new Document();
        doc = doc.implementation.createHTMLDocument();
        let smdtrx = new MetadataTransfer();
        smdtrx.set("goober", data1);
        smdtrx.set("gomer", data2)
        smdt.serializeMetadataTransferFactory(doc, smdtrx)();
        mdtrx = null;
    });

    it('browser side', function() {
        mdtrx = mdt.initBrowserMetadataTransfer(doc);
        expect(mdtrx.get("goober")).toEqual(data1);
        expect(mdtrx.get("gomer")).toEqual(data2);
        expect(mdtrx.labels().length).toBe(2);
    });
});
