# The agent applies a Chain of Thought (CoT) reasoning approach to optimise Kubernetes cluster costs
# by right-sizing resource requests based on actual usage and forecasted demand
#
# It uses a single decision point for target VM count and budget calculation to ensure consistency
# throughout the reasoning steps
#
# It follows a structured 5-step reasoning process:
# 1. Understand Current State
# 2. Diagnose Waste
# 3. Generate Right-Sizing Recommendations
# 4. Calculate Target Resource Budget
# 5. Cost Impact Analysis

from langchain_ollama import ChatOllama
import json
import re
import math

class KubernetesCostOptimiser:
    def __init__(self):
        self.llm = ChatOllama(model="qwen2.5:7b")
        self.reasoning_chain = []
        self.target_vm_count = None  
        self.target_budget = None    #
    
    def ask_and_answer(self, step_name, question, context):
        """Ask the LLM a question and store reasoning"""
        prompt = f"""You are a Kubernetes cost optimisation expert analyzing resource efficiency.

{question}

Context:
{context}

Provide a detailed, analytical answer with specific numbers and clear reasoning."""
        
        response = self.llm.invoke(prompt)
        answer = response.content
        
        self.reasoning_chain.append({
            "step": step_name,
            "question": question,
            "answer": answer
        })
        
        print(f"\n{'='*80}")
        print(f"💡 {step_name}")
        print(f"{'='*80}")
        print(f"{question}\n")
        print(answer)
        
        return answer
    
    def calculate_current_state(self, current_requests_with_replicas, actual_usage):
        """Pre-calculate current state metrics"""
        total_cpu_requests = sum(svc['total_cpu'] for svc in current_requests_with_replicas.values())
        total_memory_requests_mb = sum(svc['total_memory'] for svc in current_requests_with_replicas.values())
        total_memory_requests_gb = total_memory_requests_mb / 1024
        
        cpu_utilization = (actual_usage['cpu_cores'] / total_cpu_requests) * 100
        memory_utilization = (actual_usage['memory_gb'] / total_memory_requests_gb) * 100
        
        cpu_waste = total_cpu_requests - actual_usage['cpu_cores']
        memory_waste = total_memory_requests_gb - actual_usage['memory_gb']
        
        cpu_waste_pct = (cpu_waste / total_cpu_requests) * 100
        memory_waste_pct = (memory_waste / total_memory_requests_gb) * 100
        
        return {
            "total_cpu_requests": total_cpu_requests,
            "total_memory_requests_gb": total_memory_requests_gb,
            "cpu_utilization": cpu_utilization,
            "memory_utilization": memory_utilization,
            "cpu_waste": cpu_waste,
            "memory_waste": memory_waste,
            "cpu_waste_pct": cpu_waste_pct,
            "memory_waste_pct": memory_waste_pct
        }
    
    def calculate_target_budget_and_vms(self, forecast_summary, actual_usage, cluster_data):
        """Programmatically calculate target budget and VM count - SINGLE DECISION POINT"""
        # Calculate target budget with 20% safety buffer
        target_cpu = max(forecast_summary['cpu_pred'] * 1.2, actual_usage['cpu_cores'])
        target_memory_gb = max((forecast_summary['mem_pred'] / 1024) * 1.2, actual_usage['memory_gb'])
        
        # Calculate VMs needed using Kubernetes scheduling formula
        vms_for_cpu = math.ceil(target_cpu / cluster_data['vm_quota']['cpu_cores'])
        vms_for_memory = math.ceil(target_memory_gb / cluster_data['vm_quota']['memory_gb'])
        target_vm_count = max(vms_for_cpu, vms_for_memory)
        
        self.target_budget = {
            'cpu_cores': target_cpu,
            'memory_gb': target_memory_gb
        }
        self.target_vm_count = target_vm_count
        
        return self.target_budget, self.target_vm_count
    
    def extract_vm_count_from_response(self, text):
        """Extract VM count from LLM response as fallback"""
        try:
            # Look for patterns like "2 VMs", "VM count: 2", "need 2 VMs"
            patterns = [
                r'(\d+)\s*VMs?',
                r'VM.*?count.*?(\d+)',
                r'need.*?(\d+).*?VMs?',
                r'required.*?(\d+).*?VMs?'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    return int(matches[0])
            
            return None
        except:
            return None
    
    def optimise_cluster(self, cluster_data, current_requests_with_replicas, forecast_summary, actual_usage):
        """AI-driven CoT optimisation workflow"""
        
        print("="*80)
        print("🤖 AI-DRIVEN KUBERNETES COST OPTIMISER")
        print("="*80)
        print("GOAL: Reduce cost by right-sizing resource requests → fewer VMs → lower cost")
        print("="*80)
        
        # Pre-compute current state
        current_state = self.calculate_current_state(current_requests_with_replicas, actual_usage)
        
        # PROGRAMMATIC DECISION: Calculate target budget and VMs once
        target_budget, target_vm_count = self.calculate_target_budget_and_vms(
            forecast_summary, actual_usage, cluster_data
        )
        
        # Display current state
        print(f"\n📊 CURRENT STATE")
        print(f"{'='*80}")
        print(f"VMs: {cluster_data['current_vm_count']} @ £{cluster_data['hourly_cost_gbp']:.2f}/hour")
        print(f"VM Quota: {cluster_data['vm_quota']['cpu_cores']} CPU cores, {cluster_data['vm_quota']['memory_gb']}GB memory per VM")
        print(f"\nResources:")
        print(f"  - CPU: {current_state['total_cpu_requests']:.2f}c requested, {actual_usage['cpu_cores']:.2f}c used ({current_state['cpu_utilization']:.1f}% utilization)")
        print(f"  - Memory: {current_state['total_memory_requests_gb']:.2f}GB requested, {actual_usage['memory_gb']:.2f}GB used ({current_state['memory_utilization']:.1f}% utilization)")
        print(f"\nWaste:")
        print(f"  - CPU: {current_state['cpu_waste']:.2f}c ({current_state['cpu_waste_pct']:.1f}% over-provisioned)")
        print(f"  - Memory: {current_state['memory_waste']:.2f}GB ({current_state['memory_waste_pct']:.1f}% over-provisioned)")
        
        # Display forecast
        print(f"\n🔮 FORECAST (Next 24 hours)")
        print(f"{'='*80}")
        print(f"CPU:")
        print(f"  - Historical average: {forecast_summary['cpu_hist']:.2f} cores")
        print(f"  - Predicted average: {forecast_summary['cpu_pred']:.2f} cores")
        print(f"\nMemory:")
        print(f"  - Historical average: {forecast_summary['mem_hist']:.1f}MB ({forecast_summary['mem_hist']/1024:.2f}GB)")
        print(f"  - Predicted average: {forecast_summary['mem_pred']:.1f}MB ({forecast_summary['mem_pred']/1024:.2f}GB)")
        
        # Display PROGRAMMATIC target decision
        print(f"\n🎯 PROGRAMMATIC TARGET DECISION")
        print(f"{'='*80}")
        print(f"Target CPU budget: {target_budget['cpu_cores']:.2f} cores (forecast + 20% buffer)")
        print(f"Target Memory budget: {target_budget['memory_gb']:.2f} GB (forecast + 20% buffer)")
        print(f"Required VMs: {target_vm_count} (max(ceil({target_budget['cpu_cores']:.2f}/2), ceil({target_budget['memory_gb']:.2f}/4)))")
        
        # ============================================================
        # AI REASONING: Chain of Thought
        # ============================================================
        print(f"\n{'='*80}")
        print("🧠 AI REASONING CHAIN")
        print(f"{'='*80}")
        
        # STEP 1: Understand Current State
        step1_context = f"""
            You need to understand the current resource efficiency situation.

            Current Cluster State:
            - VMs: {cluster_data['current_vm_count']} VMs @ £{cluster_data['hourly_cost_gbp']:.2f}/hour
            - Each VM provides: {cluster_data['vm_quota']['cpu_cores']} CPU cores, {cluster_data['vm_quota']['memory_gb']}GB memory

            Resource Requests vs Actual Usage:
            - CPU: {current_state['total_cpu_requests']:.2f} cores requested → {actual_usage['cpu_cores']:.2f} cores actually used
            - Utilization: {current_state['cpu_utilization']:.1f}%
            - Waste: {current_state['cpu_waste']:.2f} cores ({current_state['cpu_waste_pct']:.1f}%)

            - Memory: {current_state['total_memory_requests_gb']:.2f}GB requested → {actual_usage['memory_gb']:.2f}GB actually used
            - Utilization: {current_state['memory_utilization']:.1f}%
            - Waste: {current_state['memory_waste']:.2f}GB ({current_state['memory_waste_pct']:.1f}%)

            Forecast for Next 24 Hours:
            - CPU: Predicted {forecast_summary['cpu_pred']:.2f} cores (currently using {actual_usage['cpu_cores']:.2f} cores)
            - Memory: Predicted {forecast_summary['mem_pred']/1024:.2f}GB (currently using {actual_usage['memory_gb']:.2f}GB)

            ANALYZE:
            1. How much resource waste exists currently?
            2. Is the waste significant enough to justify optimisation?
            3. What does the forecast tell us about future resource needs?

            Provide a SHORT conclusion (2-3 sentences maximum) summarizing the waste situation and whether action is needed.
            """
        self.ask_and_answer(
            "STEP 1: Understand Current State",
            "Analyze the current resource efficiency. How much waste exists between what we request vs what we actually use?",
            step1_context
        )
        
        # STEP 2: Diagnose Waste
        step2_context = f"""
            Now look at each individual service to identify where the waste is coming from.

            All 12 Services in Default Namespace (each has 3 replicas):

            {json.dumps(current_requests_with_replicas, indent=2)}

            Key Observations:
            - All services request 250MB memory per pod (uniform - likely not optimised)
            - CPU requests vary: 0.025c to 0.511c per pod
            - Total across all services:
            - CPU: {current_state['total_cpu_requests']:.2f} cores requested
            - Memory: {current_state['total_memory_requests_gb']:.2f}GB requested

            Actual Cluster Usage:
            - CPU: {actual_usage['cpu_cores']:.2f} cores ({current_state['cpu_utilization']:.1f}% of requested)
            - Memory: {actual_usage['memory_gb']:.2f}GB ({current_state['memory_utilization']:.1f}% of requested)

            Service Type Patterns (typical workloads):
            - Frontend/High-traffic (frontend, cartservice, checkoutservice): Need more resources
            - Backend/Processing (productcatalogservice, recommendationservice, currencyservice): Moderate needs
            - Lightweight/Utility (emailservice, paymentservice, shippingservice): Minimal needs
            - Infrastructure (redis-cart): Stable, predictable
            - Testing (loadgenerator): Can be optimised aggressively

            IDENTIFY:
            Which services are likely over-provisioned based on their type? List the top candidates for right-sizing with ONE sentence justification each.
            Keep it SHORT and ACTIONABLE.
            """
        self.ask_and_answer(
            "STEP 2: Diagnose Waste",
            "Looking at all 12 services, identify which ones are over-provisioned and should be prioritized for right-sizing.",
            step2_context
        )
        
        # STEP 3: Calculating Target Resource Budget
        step3_context = f"""
            Based on the forecast and current usage, determine what our target resource budget should be.

            Current Situation:
            - Requesting: {current_state['total_cpu_requests']:.2f}c CPU, {current_state['total_memory_requests_gb']:.2f}GB Memory
            - Using: {actual_usage['cpu_cores']:.2f}c CPU, {actual_usage['memory_gb']:.2f}GB Memory
            - Forecast (next 24h): {forecast_summary['cpu_pred']:.2f}c CPU, {forecast_summary['mem_pred']/1024:.2f}GB Memory

            Safety Considerations:
            - We need a safety buffer for traffic spikes
            - Industry standard: 20% buffer above forecast
            - Cannot reduce below actual usage

            VM Capacity:
            - Each VM provides: {cluster_data['vm_quota']['cpu_cores']} CPU cores, {cluster_data['vm_quota']['memory_gb']}GB memory
            - Kubernetes scheduling: Must satisfy BOTH CPU AND Memory constraints
            - VM count = max(ceil[Total CPU / CPU per VM], ceil[Total Memory / Memory per VM])

            PROGRAMMATIC CALCULATION (for reference):
            - Target CPU: {target_budget['cpu_cores']:.2f} cores (max(forecast × 1.2, actual usage))
            - Target Memory: {target_budget['memory_gb']:.2f} GB (max(forecast × 1.2, actual usage))  
            - Required VMs: {target_vm_count}

            DECIDE:
            Verify the programmatic calculation above. Do you agree with this target budget and VM count?
            Explain WHY this is the right target, considering both safety and efficiency.
            """
        target_decision = self.ask_and_answer(
            "STEP 3: Calculating Target Resource Budget",
            "Based on the forecast and safety requirements, verify the target budget and VM count. Do you agree with this approach?",
            step3_context
        )
        
        # STEP 4: Generating Specific Recommendations
        step4_context = f"""
            Now provide SPECIFIC per-pod CPU and Memory request changes for each service.

            Current Service Configurations:
            {json.dumps(current_requests_with_replicas, indent=2)}

            Your Target Budget (from Step 3):
            - Target CPU: {target_budget['cpu_cores']:.2f} cores
            - Target Memory: {target_budget['memory_gb']:.2f} GB
            - Target VMs: {target_vm_count}

            Constraints:
            - Keep 3 replicas per service (DO NOT change replica counts)
            - Only modify per-pod CPU and Memory requests
            - Total across all services must fit within your target budget
            - Maintain performance for critical services
            - Be specific with numbers (e.g., "0.400c CPU, 180MB memory per pod")

            Output Format for ALL 12 services:
            ---
            Service: <name>
            Current per-pod: <X>c CPU, <Y>MB Memory
            Recommended per-pod: <X>c CPU, <Y>MB Memory
            Reduction: <X>c CPU, <Y>MB Memory per pod
            Reason: <specific justification>
            ---

            PROVIDE:
            Specific recommendations for all 12 services with exact numbers.
            """
        recommendations = self.ask_and_answer(
            "STEP 4: Generating Right-Sizing Recommendations",
            "Provide SPECIFIC per-pod CPU and Memory request changes for ALL 12 services to meet the target budget.",
            step4_context
        )
        
        # STEP 5: Cost Impact Analysis
        step5_context = f"""
            Calculate the cost impact of your optimisation.

            Current Cost:
            - VMs: {cluster_data['current_vm_count']}
            - Cost per VM: £{cluster_data['hourly_cost_gbp'] / cluster_data['current_vm_count']:.2f}/hour
            - Total: £{cluster_data['hourly_cost_gbp']:.2f}/hour

            Your optimised State (FIXED DECISION from Step 3):
            - Target VMs: {target_vm_count} VMs (this is fixed - use this number)
            - New total cost: (calculate based on {target_vm_count} VMs)

            CALCULATE:
            1. Hourly cost after optimisation
            2. Hourly savings
            3. Daily, monthly, yearly savings
            4. Percentage reduction
            5. Is this worth the implementation effort?

            Keep it concise - just the numbers and a brief final recommendation.
            """
        cost_analysis = self.ask_and_answer(
            "STEP 5: Cost Impact Analysis",
            f"Calculate the cost savings from your optimisation using {target_vm_count} VMs. What's the financial impact?",
            step5_context
        )
        
        # ============================================================
        # FINAL SUMMARY (using programmatic decisions)
        # ============================================================
        print(f"\n{'='*80}")
        print("💰 OPTIMISATION SUMMARY")
        print(f"{'='*80}")
        
        # Calculate costs based on PROGRAMMATIC decision
        cost_per_vm = cluster_data['hourly_cost_gbp'] / cluster_data['current_vm_count']
        ai_cost = target_vm_count * cost_per_vm
        ai_savings = cluster_data['hourly_cost_gbp'] - ai_cost
        
        summary = {
            "current_state": {
                "vm_count": cluster_data['current_vm_count'],
                "hourly_cost": cluster_data['hourly_cost_gbp'],
                "cpu_requested": current_state['total_cpu_requests'],
                "memory_requested_gb": current_state['total_memory_requests_gb'],
                "cpu_used": actual_usage['cpu_cores'],
                "memory_used_gb": actual_usage['memory_gb'],
                "cpu_utilization_pct": current_state['cpu_utilization'],
                "memory_utilization_pct": current_state['memory_utilization'],
                "cpu_waste_pct": current_state['cpu_waste_pct'],
                "memory_waste_pct": current_state['memory_waste_pct']
            },
            "programmatic_decisions": {
                "target_cpu_budget": target_budget['cpu_cores'],
                "target_memory_budget": target_budget['memory_gb'],
                "recommended_vm_count": target_vm_count,
                "estimated_hourly_cost": ai_cost,
                "estimated_hourly_savings": ai_savings
            },
            "reasoning_chain": self.reasoning_chain
        }
        
        print(f"\n📊 Current State:")
        print(f"   - {cluster_data['current_vm_count']} VMs @ £{cluster_data['hourly_cost_gbp']:.2f}/hour")
        print(f"   - Requesting: {current_state['total_cpu_requests']:.2f}c CPU, {current_state['total_memory_requests_gb']:.2f}GB Memory")
        print(f"   - Using: {actual_usage['cpu_cores']:.2f}c CPU ({current_state['cpu_utilization']:.1f}%), {actual_usage['memory_gb']:.2f}GB Memory ({current_state['memory_utilization']:.1f}%)")
        print(f"   - Waste: {current_state['cpu_waste_pct']:.1f}% CPU, {current_state['memory_waste_pct']:.1f}% Memory")
        
        print(f"\n🎯 Programmatic Decisions:")
        print(f"   - Target CPU: {target_budget['cpu_cores']:.2f} cores")
        print(f"   - Target Memory: {target_budget['memory_gb']:.2f} GB")
        print(f"   - Target VMs: {target_vm_count}")
        print(f"   - Estimated cost: £{ai_cost:.2f}/hour")
        print(f"   - Estimated savings: £{ai_savings:.2f}/hour ({(ai_savings/cluster_data['hourly_cost_gbp'])*100:.1f}%)")
        print(f"   - Annual savings: £{ai_savings * 24 * 365:.2f}")
        
        print(f"\n✅ Next Steps:")
        print(f"   1. Review the 5 reasoning steps above")
        print(f"   2. Validate AI's service-specific recommendations") 
        print(f"   3. Apply changes to YAML manifests")
        print(f"   4. Commit to Git → ArgoCD deploys")
        print(f"   5. Monitor for 24-48 hours")
        
        print(f"\n{'='*80}")
        
        return summary


# ============================================================
# EXAMPLE USAGE (unchanged)
# ============================================================
if __name__ == "__main__":
    # Current service requests (3 replicas each, uniform 250MB memory)
    current_requests_with_replicas = {
        "adservice": {"replicas": 3, "per_pod_cpu": 0.063, "per_pod_memory": 250, "total_cpu": 0.189, "total_memory": 750},
        "cartservice": {"replicas": 3, "per_pod_cpu": 0.203, "per_pod_memory": 250, "total_cpu": 0.609, "total_memory": 750},
        "checkoutservice": {"replicas": 3, "per_pod_cpu": 0.035, "per_pod_memory": 250, "total_cpu": 0.105, "total_memory": 750},
        "currencyservice": {"replicas": 3, "per_pod_cpu": 0.379, "per_pod_memory": 250, "total_cpu": 1.137, "total_memory": 750},
        "emailservice": {"replicas": 3, "per_pod_cpu": 0.025, "per_pod_memory": 250, "total_cpu": 0.075, "total_memory": 750},
        "frontend": {"replicas": 3, "per_pod_cpu": 0.511, "per_pod_memory": 250, "total_cpu": 1.533, "total_memory": 750},
        "loadgenerator": {"replicas": 3, "per_pod_cpu": 0.078, "per_pod_memory": 250, "total_cpu": 0.234, "total_memory": 750},
        "paymentservice": {"replicas": 3, "per_pod_cpu": 0.025, "per_pod_memory": 250, "total_cpu": 0.075, "total_memory": 750},
        "productcatalogservice": {"replicas": 3, "per_pod_cpu": 0.323, "per_pod_memory": 250, "total_cpu": 0.969, "total_memory": 750},
        "recommendationservice": {"replicas": 3, "per_pod_cpu": 0.323, "per_pod_memory": 250, "total_cpu": 0.969, "total_memory": 750},
        "redis-cart": {"replicas": 3, "per_pod_cpu": 0.035, "per_pod_memory": 250, "total_cpu": 0.105, "total_memory": 750},
        "shippingservice": {"replicas": 3, "per_pod_cpu": 0.035, "per_pod_memory": 250, "total_cpu": 0.105, "total_memory": 750}
    }
    
    # Actual usage from Grafana monitoring
    actual_usage = {
        "cpu_cores": 2.49,
        "memory_gb": 2.06
    }
    
    # Forecast from Prophet model (next 24h)
    forecast_summary = {
        "cpu_hist": 2.233,      # Historical avg
        "cpu_pred": 2.073,      # Predicted avg
        "mem_hist": 1625.5,     # MB
        "mem_pred": 1017.8      # MB
    }
    
    # Cluster configuration
    cluster_data = {
        "current_vm_count": 4,
        "hourly_cost_gbp": 0.16,
        "vm_quota": {
            "cpu_cores": 2,      # Per VM
            "memory_gb": 4       # Per VM
        }
    }
    
    # Run optimisation
    agent = KubernetesCostOptimiser()
    result = agent.optimise_cluster(
        cluster_data,
        current_requests_with_replicas,
        forecast_summary,
        actual_usage
    )
    
    # Save full reasoning chain
    with open("optimisation_decisions.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\n💾 Full reasoning chain saved to: optimisation_decisions.json")