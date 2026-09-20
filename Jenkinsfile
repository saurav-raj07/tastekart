pipeline {
    agent any

    environment {
        // AWS ECR Configuration - Update AWS_ACCOUNT_ID and AWS_REGION to match your AWS setup
        AWS_ACCOUNT_ID   = '123456789012'
        AWS_REGION       = 'us-east-1'
        ECR_REPO_NAME    = 'tastekart-backend'
        ECR_REGISTRY     = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        
        KUBE_NAMESPACE   = 'tastekart'
        IMAGE_TAG        = "${BUILD_NUMBER}"
        
        // Jenkins Credentials IDs (configured in Jenkins Credentials Manager)
        AWS_CRED_ID      = 'aws-ecr-credentials'  // AWS credentials ID in Jenkins (UsernameWithPassword or AWS Credentials Plugin)
        KUBECONFIG_CRED  = 'kubeconfig-credentials' // Jenkins credentials ID for Kubeconfig (if needed)
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
                echo "Building commit: ${env.GIT_COMMIT}"
            }
        }

        stage('Lint & Verification') {
            steps {
                echo 'Checking Python backend syntax...'
                sh 'python3 -m compileall -q backend'

                echo 'Checking JavaScript frontend syntax...'
                sh '''
                    for file in $(find frontend/scripts -name "*.js"); do
                        node --check "$file" || exit 1
                    done
                '''
            }
        }

        stage('AWS ECR Login & Docker Build') {
            steps {
                script {
                    echo "Logging into AWS ECR registry: ${ECR_REGISTRY}"
                    
                    // If using AWS CLI credentials on Jenkins worker:
                    sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                    
                    // Alternatively, using Jenkins Credentials plugin:
                    // withCredentials([usernamePassword(credentialsId: AWS_CRED_ID, usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                    //     sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                    // }

                    echo "Building Docker image: ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG}"
                    sh "docker build -t ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} -t ${ECR_REGISTRY}/${ECR_REPO_NAME}:latest ."
                }
            }
        }

        stage('Push Image to AWS ECR') {
            steps {
                script {
                    echo "Pushing Docker images to AWS ECR..."
                    sh "docker push ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG}"
                    sh "docker push ${ECR_REGISTRY}/${ECR_REPO_NAME}:latest"
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                script {
                    echo "Deploying to Kubernetes namespace: ${KUBE_NAMESPACE}"
                    
                    // Apply Kubernetes manifests
                    sh 'kubectl apply -f k8s/namespace.yaml'
                    sh 'kubectl apply -f k8s/configmap.yaml'
                    sh 'kubectl apply -f k8s/secret.yaml'
                    sh 'kubectl apply -f k8s/mongodb.yaml'
                    sh 'kubectl apply -f k8s/user-service.yaml'
                    sh 'kubectl apply -f k8s/catalog-service.yaml'
                    sh 'kubectl apply -f k8s/order-service.yaml'
                    sh 'kubectl apply -f k8s/partner-service.yaml'
                    sh 'kubectl apply -f k8s/app-gateway.yaml'

                    echo "Updating Kubernetes deployment images from ECR..."
                    sh "kubectl set image deployment/user-service user-service=${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} -n ${KUBE_NAMESPACE}"
                    sh "kubectl set image deployment/catalog-service catalog-service=${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} -n ${KUBE_NAMESPACE}"
                    sh "kubectl set image deployment/order-service order-service=${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} -n ${KUBE_NAMESPACE}"
                    sh "kubectl set image deployment/partner-service partner-service=${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} -n ${KUBE_NAMESPACE}"
                    sh "kubectl set image deployment/app-gateway app-gateway=${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} -n ${KUBE_NAMESPACE}"

                    echo "Verifying rollout status..."
                    sh "kubectl rollout status deployment/app-gateway -n ${KUBE_NAMESPACE} --timeout=120s"
                }
            }
        }

        stage('Post-Deploy Health Check') {
            steps {
                script {
                    echo "Running health check on API Gateway..."
                    sh 'kubectl exec -n tastekart deployment/app-gateway -- curl -s http://localhost:3001/api/health | grep -q "ok" || exit 1'
                    echo "Deployment successfully verified!"
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo "TasteKart microservices pipeline executed and pushed to AWS ECR successfully!"
        }
        failure {
            echo "Pipeline failed! Please check stage logs."
        }
    }
}

