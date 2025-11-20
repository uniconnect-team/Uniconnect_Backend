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
    }

    post {
        always {
            cleanWs()
        }
    }
}
