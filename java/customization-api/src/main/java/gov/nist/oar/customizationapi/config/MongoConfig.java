/**
 * This software was developed at the National Institute of Standards and Technology by employees of
 * the Federal Government in the course of their official duties. Pursuant to title 17 Section 105
 * of the United States Code this software is not subject to copyright protection and is in the
 * public domain. This is an experimental system. NIST assumes no responsibility whatsoever for its
 * use by other parties, and makes no guarantees, expressed or implied, about its quality,
 * reliability, or any other characteristic. We would appreciate acknowledgement if the software is
 * used. This software can be redistributed and/or modified freely provided that any derivative
 * works bear some notice that they are derived from it, and any modified versions bear some notice
 * that they have been modified.
 * @author: Deoyani Nandrekar-Heinis
 */
package gov.nist.oar.customizationapi.config;

import java.util.ArrayList;
import java.util.List;

import javax.annotation.PostConstruct;

import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import com.mongodb.Mongo;
import com.mongodb.MongoClient;
import com.mongodb.MongoClientOptions;
import com.mongodb.MongoCredential;
import com.mongodb.ServerAddress;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoDatabase;

@Configuration
@ConfigurationProperties
@EnableAutoConfiguration
/**
 * MongoDB configuration, reading all the server details from config server.
 * 
 * @author Deoyani Nandrekar-Heinis
 *
 */

public class MongoConfig {

	private static Logger log = LoggerFactory.getLogger(MongoConfig.class);

	MongoClient mongoClient;

	private MongoDatabase mongoDb;
	private MongoCollection<Document> recordsCollection;
	private MongoCollection<Document> changesCollection;
	private String metadataServerUrl = "";
	List<ServerAddress> servers = new ArrayList<ServerAddress>();

	@Value("${oar.mdserver:testserver}")
	private String mdserver;
	@Value("${oar.dbcollections.records: records}")
	private String record;
	@Value("${oar.dbcollections.changes: changes}")
	private String changes;
	@Value("${oar.mongodb.port:3333}")
	private int port;
	@Value("${oar.mongodb.host:localhost}")
	private String host;
	@Value("${oar.mongodb.database.name:UpdateDB}")
	private String dbname;
	@Value("${oar.mongodb.readwrite.user:testuser}")
	private String user;
	@Value("${oar.mongodb.readwrite.password:testpassword}")
	private String password;
	@Value("${oar.mdserver.secret:secret}")
	private String mdserversecret;

	@PostConstruct
	public void initIt() throws Exception {

		mongoClient = (MongoClient) this.mongo();
		log.info("########## " + dbname + " ########");

		this.setMongodb(this.dbname);
		this.setRecordCollection(this.record);
		this.setChangeCollection(this.changes);
		this.setMetadataServer(this.mdserver);

	}

	/**
	 * Get mongodb database name
	 * 
	 * @return
	 */

	public MongoDatabase getMongoDb() {
		return mongoDb;
	}

	/**
	 * Set mongodb database name
	 * 
	 * @param dbname
	 */
	private void setMongodb(String dbname) {
		mongoDb = mongoClient.getDatabase(dbname);
	}

	/***
	 * Get records collection from Mongodb
	 * 
	 * @return
	 */
	public MongoCollection<Document> getRecordCollection() {
		return recordsCollection;
	}

	/**
	 * Set records collection
	 */
	private void setRecordCollection(String record) {
		recordsCollection = mongoDb.getCollection(record);
	}

	/***
	 * Get changes collection from Mongodb
	 * 
	 * @return
	 */
	public MongoCollection<Document> getChangeCollection() {
		return changesCollection;
	}

	/**
	 * Set changes collection
	 */
	private void setChangeCollection(String change) {
		changesCollection = mongoDb.getCollection(change);
	}

	/**
	 * Get Metadata service URL
	 * 
	 * @return
	 */
	public String getMetadataServer() {
		return this.metadataServerUrl;
	}

	private void setMetadataServer(String mserver) {
		this.metadataServerUrl = mserver;
	}

	/**
	 * Get Metadata service secret to communicate with API
	 * 
	 * @return
	 */
	public String getMDSecret() {
		return this.mdserversecret;
	}

	/**
	 * MongoClient : Initialize mongoclient for db operations
	 * 
	 * @return
	 * @throws Exception
	 */
	public Mongo mongo() throws Exception {
		servers.add(new ServerAddress(host, port));
		return new MongoClient(servers, MongoCredential.createCredential(user, dbname, password.toCharArray()),
				MongoClientOptions.builder().build());
	}
}
