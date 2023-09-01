local config = import "../skiff.json";
local util = import "./util.libsonnet";

function(image, cause, sha, env="prod", branch="", repo="", buildId="")
	local domains =
		util.getHosts(env, config, ".apps.allenai.org") +
		util.getHosts(env, config, ".allen.ai") +
		if env == "prod" && "customDomains" in config then
			config.customDomains else
		[];
	local grouped = util.groupHosts(
		domains,
		[".allenai.org", ".allen.ai", ".semanticscholar.org" ]
	);
	local canonical = grouped[0];
	local extra = grouped[1];
	local allenAIHosts = canonical[".allen.ai"];
	local scholarHosts = canonical[".semanticscholar.org"];
	local hosts = canonical[".allenai.org"] + extra;

	local numReplicas = if env == "prod" then config.replicas.prod else 1;

	local namespaceName = config.appName;
	local fullyQualifiedName = config.appName + "-" + env;

	local namespaceLabels = {
		app: config.appName,
		contact: config.contact,
		team: config.team
	};

	local labels = namespaceLabels + {
		env: env
	};

	local selectorLabels = {
		app: config.appName,
		env: env
	};

	local antiAffinityLabels = {
		onlyOneOfPerNode: config.appName + "-" + env
	};
	local podLabels = labels + antiAffinityLabels;

	local annotations = {
		"apps.allenai.org/sha": sha,
		"apps.allenai.org/branch": branch,
		"apps.allenai.org/repo": repo,
		"apps.allenai.org/build": buildId
	};

	local port = 3000;

	local namespace = {
		apiVersion: "v1",
		kind: "Namespace",
		metadata: {
			name: namespaceName,
			labels: namespaceLabels
		}
	};

	local tls = util.getTLSConfig(fullyQualifiedName, hosts);
	local ingress = {
		apiVersion: "networking.k8s.io/v1",
		kind: "Ingress",
		metadata: {
			name: fullyQualifiedName,
			namespace: namespaceName,
			labels: labels,
			annotations: annotations + tls.ingressAnnotations + util.getAuthAnnotations(config, ".apps.allenai.org") + {
				"nginx.ingress.kubernetes.io/ssl-redirect": "true"
			}
		},
		spec: {
			tls: [ tls.spec + { hosts: hosts } ],
			rules: [
				{
					host: host,
					http: {
						paths: [
							{
								path: "/",
								pathType: "Prefix",
								backend: {
									service: {
										name: fullyQualifiedName,
										port: {
											number: port
										}
									}
								}
							}
						]
					}
				} for host in hosts
			]
		}
	};

	local allenAITLS = util.getTLSConfig(fullyQualifiedName + "-allen-dot-ai", allenAIHosts);
	local allenAIIngress = {
		apiVersion: "networking.k8s.io/v1",
		kind: "Ingress",
		metadata: {
			name: fullyQualifiedName + "-allen-dot-ai",
			namespace: namespaceName,
			labels: labels,
			annotations: annotations + allenAITLS.ingressAnnotations + util.getAuthAnnotations(config, ".allen.ai") + {
				"nginx.ingress.kubernetes.io/ssl-redirect": "true"
			}
		},
		spec: {
			tls: [ allenAITLS.spec + { hosts: allenAIHosts } ],
			rules: [
				{
					host: host,
					http: {
						paths: [
							{
								path: "/",
								pathType: "Prefix",
								backend: {
									service: {
										name: fullyQualifiedName,
										port: {
											number: port
										}
									}
								}
							}
						]
					}
				} for host in allenAIHosts
			]
		}
	};

	local scholarTLS = util.getTLSConfig(fullyQualifiedName + "-scholar", scholarHosts);
	local scholarIngress = {
		apiVersion: "networking.k8s.io/v1",
		kind: "Ingress",
		metadata: {
			name: fullyQualifiedName + "-scholar",
			namespace: namespaceName,
			labels: labels,
			annotations: annotations + scholarTLS.ingressAnnotations + util.getAuthAnnotations(config, "apps.semanticscholar.org") + {
				"nginx.ingress.kubernetes.io/ssl-redirect": "true"
			}
		},
		spec: {
			tls: [ scholarTLS.spec + { hosts: scholarHosts } ],
			rules: [
				{
					host: host,
					http: {
						paths: [
							{
								path: "/",
								pathType: "Prefix",
								backend: {
									service: {
										name: fullyQualifiedName,
										port: {
											number: port
										}
									}
								}
							}
						]
					}
				} for host in scholarHosts
			]
		}
	};

	local deployment = {
		apiVersion: "apps/v1",
		kind: "Deployment",
		metadata: {
			labels: labels,
			name: fullyQualifiedName,
			namespace: namespaceName,
			annotations: annotations + {
				"kubernetes.io/change-cause": cause
			}
		},
		spec: {
			strategy: {
				type: "RollingUpdate",
				rollingUpdate: {
					maxSurge: numReplicas
				}
			},
			revisionHistoryLimit: 3,
			replicas: numReplicas,
			selector: {
				matchLabels: selectorLabels
			},
			template: {
				metadata: {
					name: fullyQualifiedName,
					namespace: namespaceName,
					labels: podLabels,
					annotations: annotations
				},
				spec: {
					affinity: {
						podAntiAffinity: {
							requiredDuringSchedulingIgnoredDuringExecution: [
								{
								   labelSelector: {
										matchExpressions: [
											{
													key: labelName,
													operator: "In",
													values: [ antiAffinityLabels[labelName], ],
											} for labelName in std.objectFields(antiAffinityLabels)
									   ],
									},
									topologyKey: "kubernetes.io/hostname"
								},
							]
						},
					},
					containers: [
						{
							name: fullyQualifiedName,
							image: image,
							readinessProbe: {
								httpGet: {
									port: port,
									scheme: "HTTP",
									path: "/?check=rdy"
								},
								periodSeconds: 10,
								failureThreshold: 3
							},
							resources: {
								requests: {
									cpu: 0.1,
									memory: "500M"
								}
							},
							env: [
								{
									name: "LOG_FORMAT",
									value: "google:json"
								}
							]
						}
					]
				}
			}
		}
	};

	local service = {
		apiVersion: "v1",
		kind: "Service",
		metadata: {
			name: fullyQualifiedName,
			namespace: namespaceName,
			labels: labels,
			annotations: annotations
		},
		spec: {
			selector: selectorLabels,
			ports: [
				{
					port: port,
					name: "http"
				}
			]
		}
	};

	local pdb = {
		apiVersion: "policy/v1beta1",
		kind: "PodDisruptionBudget",
		metadata: {
			name: fullyQualifiedName,
			namespace: namespaceName,
			labels: labels,
		},
		spec: {
			minAvailable: if numReplicas > 1 then 1 else 0,
			selector: {
				matchLabels: selectorLabels,
			},
		},
	};

	local defaultObjects = [
		namespace,
		ingress,
		allenAIIngress,
		deployment,
		service,
		pdb
	];

	if std.length(scholarHosts) > 0 then
		defaultObjects + [ scholarIngress ]
	else
		defaultObjects

