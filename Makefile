REDIS_POD := $(shell kubectl get pods -l app=redis -n databases -o jsonpath="{.items[0].metadata.name}")
.PHONY: help bridge debug argocd tunnel agent learner payload

help: 
	@echo "Make sure your k8s cluster is running"
	@echo "Usage:"
	@echo "make argocd 		-> start argocd port-forward"
	@echo "make bridge 		-> start redis port-forward"
	@echo "make debug 		-> start exec redis debug pod"
	@echo "make tunnel 		-> start public url tunnel"
	@echo "make agent  		-> start the agent"
	@echo "make learner 		-> start the webhook server"	
	@echo "make payload 		-> create test payloads"	

argocd: 
	@echo "Connecting to ArgoCD service"
	kubectl port-forward svc/argocd-server -n argocd 9000:80

bridge:
	@echo "Connecting to Redis service"
	kubectl port-forward svc/redis-master -n databases 6379:6379

debug: 
	@echo "Connecting to Redis pod: $(REDIS_POD)"
	kubectl exec -it $(REDIS_POD) -n databases -- bash 


tunnel:
	@echo "Creating public url with localhost.run"
	@echo "copy the url from the output below and paste it into GitHub webhook settings"
	@ssh -R 80:localhost:8010 key@localhost.run

agent:
	@echo "Starting the agent"
	python3 agent/main.py

learner:
	@echo "Starting the webhook server (learner)"
	python3 agent/learner.py

payload:
	@echo "Generating test payloads"
	@echo "Quering Prometheus..."
	python scripts/generate_test_payload.py > test_payloads/cost_$(shell date +%Y%m%d).json
