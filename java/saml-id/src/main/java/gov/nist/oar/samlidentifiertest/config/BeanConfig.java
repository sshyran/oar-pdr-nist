/*
 * Copyright 2002-2018 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 *
 */

package gov.nist.oar.samlidentifiertest.config;

import java.util.ArrayList;
import java.util.List;

import javax.lang.model.element.ModuleElement.UsesDirective;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.saml.provider.SamlServerConfiguration;
import org.springframework.security.saml.provider.identity.config.SamlIdentityProviderServerBeanConfiguration;

@Configuration
public class BeanConfig extends SamlIdentityProviderServerBeanConfiguration {
	private final AppConfig config;

	public BeanConfig(AppConfig config) {
		this.config = config;
	}

	@Override
	protected SamlServerConfiguration getDefaultHostSamlServerConfiguration() {
		return config;
	}

	@Bean
	public UserDetailsService userDetailsService() {
		List<UserDetails> users = new ArrayList();
		UserDetails userDetails = User.withDefaultPasswordEncoder()
			.username("user")
			.password("password")
			.roles("USER")
			.build();
		users.add(userDetails);
		
		UserDetails user1Details = User.withDefaultPasswordEncoder()
				.username("testuser")
				.password("testpassword")
				.roles("USER")
				.build();
		users.add(user1Details);
		
		UserDetails user2Details = User.withDefaultPasswordEncoder()
				.username("newuser")
				.password("newpassword")
				.roles("USER")
				.build();
		users.add(user2Details);
		
		
		return new InMemoryUserDetailsManager(users);
	}
}