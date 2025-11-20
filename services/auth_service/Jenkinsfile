pipeline {
    agent any

    options {
        skipStagesAfterUnstable()
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build auth-service image') {
            steps {
                script {
                    if (isUnix()) {
                        sh """
                            set -e
                            docker build -f services/auth_service/Dockerfile -t auth-service:latest .
                        """
                    } else {
                        bat """
                            docker build -f services/auth_service/Dockerfile -t auth-service:latest .
                        """
                    }
                }
            }
        }

        stage('Load into Minikube') {
            steps {
                script {
                    if (isUnix()) {
                        sh """
                            set -e
                            minikube image load auth-service:latest
                        """
                    } else {
                        bat """
                            minikube image load auth-service:latest
                        """
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                script {
                    if (isUnix()) {
                        sh """
                            set -e
                            # Use minikube's kubectl wrapper so the correct cluster/context is used
                            minikube kubectl -- apply -f k8s/auth-service.yaml
                        """
                    } else {
                        bat """
                            REM Use minikube's kubectl wrapper so the correct cluster/context is used
                            minikube kubectl -- apply -f k8s/auth-service.yaml
                        """
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
