package gov.nist.oar.custom.customizationapi.config.JWTConfig;

import java.io.IOException;
import java.text.ParseException;
import java.util.List;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

import org.json.simple.JSONObject;
import org.opensaml.saml2.core.Attribute;
import org.opensaml.xml.schema.impl.XSAnyImpl;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.saml.SAMLCredential;
import org.springframework.security.web.authentication.AbstractAuthenticationProcessingFilter;

import com.nimbusds.jose.JWSObject;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;

import gov.nist.oar.custom.customizationapi.helpers.ExtractUserId;
import gov.nist.oar.custom.customizationapi.helpers.domains.UserToken;

/**
 * This filter users JWT configuration and filters all the service requests
 * which need authenticated token exchange.
 * 
 * @author Deoyani Nandrekar-Heinis
 *
 */

public class JWTAuthenticationFilter extends AbstractAuthenticationProcessingFilter {

    private static final Logger logger = LoggerFactory.getLogger(JWTAuthenticationFilter.class);
    public static final String Header_Authorization_Token = "Authorization";

    public JWTAuthenticationFilter(final String matcher, AuthenticationManager authenticationManager) {
	super(matcher);
	super.setAuthenticationManager(authenticationManager);
    }

    @Override
    public Authentication attemptAuthentication(HttpServletRequest request, HttpServletResponse response)
	    throws IOException, ServletException {

	logger.info("Attempt to check token and  authorized token validity");
	String token = request.getHeader(Header_Authorization_Token);
	if (token != null)
	    token = token.substring(7).trim();
	String userId = ExtractUserId.getUserId();
	String recordId = "";
	try {
	    recordId = request.getRequestURI().split("/draft/")[1];
	} catch (ArrayIndexOutOfBoundsException exp) {
	    try {
		recordId = request.getRequestURI().split("/savedrecord/")[1];
	    } catch (Exception ex) {

	    }
	}

	try {

	    SignedJWT signedJWTtest = SignedJWT.parse(token);
	    JWTClaimsSet claimsSet = JWTClaimsSet.parse(signedJWTtest.getPayload().toJSONObject());
	    String testSubject = claimsSet.getSubject();
	    String[] customSubject = testSubject.split("\\|");
	    String tokenUser = customSubject[0];
	    String tokenRecord = customSubject[1];

	    if (!(userId.equals(tokenUser) && recordId.equals(tokenRecord)))
		throw new IOException("Unauthorized user:");
	    System.out.println(signedJWTtest.getParsedString());
	} catch (ParseException e) {
	    // TODO Auto-generated catch block
	    e.printStackTrace();
	}

	JWTAuthenticationToken jwtAuthenticationToken = new JWTAuthenticationToken(token);

	return getAuthenticationManager().authenticate(jwtAuthenticationToken);
    }

    @Override
    protected void successfulAuthentication(HttpServletRequest request, HttpServletResponse response, FilterChain chain,
	    Authentication authResult) throws IOException, ServletException {
//	boolean b = SecurityContextHolder.getContext().getAuthentication().isAuthenticated();
//        SecurityContextHolder.getContext().setAuthentication(authResult);
	logger.info("If token is authorized redirect to original request.");
	chain.doFilter(request, response);
    }

    @Override
    protected void unsuccessfulAuthentication(HttpServletRequest request, HttpServletResponse response,
	    AuthenticationException failed) throws IOException, ServletException {
//        SecurityContextHolder.clearContext();
	Authentication auth = SecurityContextHolder.getContext().getAuthentication();
	String userId = "";
	if (auth != null) {
//	    auth.getName();
//	    SAMLCredential credential = (SAMLCredential) auth.getCredentials();
//	    List<Attribute> attributes = credential.getAttributes();
//	    org.opensaml.xml.schema.impl.XSAnyImpl xsImpl = (XSAnyImpl) attributes.get(0).getAttributeValues().get(0);
//	    userId = xsImpl.getTextContent();
	    userId = ExtractUserId.getUserId();
	}
	logger.info("If token is not authorized send Unauthorized status.");
	response.setStatus(HttpStatus.UNAUTHORIZED.value());
	response.setContentType(MediaType.APPLICATION_JSON_VALUE);
	JSONObject jObject = new JSONObject();
	if (!userId.isEmpty()) {
	    jObject.put("userId", userId);
	    jObject.put("message", "User is not Authorized.");
	} else {
	    jObject.put("message", "User is not Authenticated.");
	}

	response.getWriter().write(jObject.toJSONString());
    }

}