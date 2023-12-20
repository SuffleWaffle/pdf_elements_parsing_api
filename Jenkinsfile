def gitCredentialsId = "github-creds"
def gitRepoUrl = 'git@github.com:Drawer-Inc/pdf_elements_parsing_service.git'
def pom = ''

def build_service = '''
        ls -al
        chmod +x ./build_service.sh
        ./build_service.sh
    '''

def build_update_version = '''
        chmod +x ./build_update_version.sh
        ./build_update_version.sh
    '''

def tag_counter = '''
    SHORT_BRANCH=`echo ${BRANCH} | awk -F "/" '{print $NF}'`
    SHORT_HASH=`git rev-parse --short=10 HEAD`
    IMAGE_TAG=${SHORT_BRANCH}-${SHORT_HASH}-${BUILD_NUMBER}
    echo "IMAGE_TAG = ${IMAGE_TAG}"
'''

properties(
  [
    parameters(
      [
        [
          $class            : 'GitParameterDefinition',
          branch            : '',
          branchFilter      : '.*',
          defaultValue      : '${env.BRANCH}',
          description       : 'Branch or Tag',
          name              : 'BRANCH',
          quickFilterEnabled: false,
          selectedValue     : 'DEFAULT',
          sortMode          : 'ASCENDING_SMART',
          tagFilter         : '*',
          type              : 'PT_BRANCH'
        ]
      ]
    ),
//test
    pipelineTriggers([
      [
      $class: 'GenericTrigger',
      genericVariables: [
        [
          key: 'BRANCH',
          value: '$.ref',
          expressionType: 'JSONPath'
        ],

      ],
        causeString: 'Triggered by Github',
        token: 'pO6WEpVmPUXwVYKIvRVsp1PvlafOevcQT0RPFUq19Yb3rdw6bIhrQVM7hcWsqrFa',
        printContributedVariables: true,
        printPostContent: true,
        silentResponse: false,
        regexpFilterText: '$BRANCH',
        regexpFilterExpression:  '^(refs/heads/stage-ci|refs/heads/eks|refs/heads/dev-ci|refs/heads/main|refs/tags/.+)$'
      ]
      ])

  ]
)
//TESTS

pipeline {
  environment {
    SERVICE_NAME    = 'pdf_elements_parsing_service'
    AWS_REGION      = 'us-east-1'
    AWS_ACCOUNT     = '064427434392'
    SLACK_DOMAIN    = 'drawerai'
    SLACK_CHANNEL   = "#ci-cd-ai"
    SLACK_TOKEN     = credentials("slack-token")
    PROD_PASSWORD   = credentials("ai-prod-password")
    STAGE_PASSWORD  = credentials("ai-stage-password")
  }

  agent any

  options {
    buildDiscarder(logRotator(numToKeepStr: '20'))
    ansiColor('xterm')
    timestamps()
  }


  stages {

    stage('Prepare') {
      steps {
        script {
          currentBuild.displayName = "#${env.BUILD_NUMBER}-${env.BRANCH}"
        }
      }
    }

    stage('Checkout') {
      steps {
        checkout(
          [
            $class           : 'GitSCM',
            branches         : [[name: "${BRANCH}"]],
            userRemoteConfigs: [[url: "${gitRepoUrl}", credentialsId: "${gitCredentialsId}"]],
          ]
        )
        echo "This branch is ${BRANCH}"
      }
    }
//test commit

    stage ('Docker Build') {
      when{
        not{
          anyOf{
            expression{env.BRANCH =~ /^refs\/heads\/rollback$/}
            expression{env.BRANCH =~ /^origin\/rollback$/}
          }
      }
    }
      steps{script { 
        sh build_service 
        env.image_tag = readFile('image_tag.txt').trim()
        echo "Read tag_image value: ${env.image_tag}"
      }}
    }

    stage('Deploy dev'){
      when {
        anyOf {
          expression {env.BRANCH =~ /^refs\/heads\/dev-ci$/}
          expression {env.BRANCH =~ /^refs\/tags\/dev-.+$/}
          expression {env.BRANCH =~ /^origin\/dev-ci$/}
        }
      }
      steps {
        script {
          sshagent(['ai-dev-creds']) {
            sh """
              scp -o StrictHostKeyChecking=no -P 9376 deploy_service.sh administrator@66.117.7.18:/home/administrator/dev/jenkins/pdf_elements_parsing_service
              ssh -o StrictHostKeyChecking=no -l administrator 66.117.7.18  -p 9376  chmod +x /home/administrator/dev/jenkins/pdf_elements_parsing_service/deploy_service.sh
              ssh -o StrictHostKeyChecking=no -l administrator 66.117.7.18  -p 9376  "cd dev/jenkins/pdf_elements_parsing_service && ./deploy_service.sh ${env.image_tag}"
            """
          }
        }
      }
    }

    stage('Deploy stage'){
      when {
        anyOf {
          expression {env.BRANCH =~ /^refs\/heads\/stage-ci$/}
          expression {env.BRANCH =~ /^refs\/heads\/eks$/}
          expression {env.BRANCH =~ /^refs\/tags\/stage-.+$/}
          expression {env.BRANCH =~ /^origin\/stage-ci$/}
          expression {env.BRANCH =~ /^origin\/eks$/}
        }
      }
      parallel{
        stage('Deploy on-prem'){
          when{anyOf{
            expression {env.BRANCH =~ /^refs\/heads\/stage-ci$/}
            expression {env.BRANCH =~ /^origin\/stage-ci$/}
          }}
          steps {
            script {
              echo "Skipping!"
              // sh """
              //   echo "Image tag is ${IMAGE_TAG}"
              //   sshpass -p $STAGE_PASSWORD scp -o StrictHostKeyChecking=no -P 9376 deploy_service.sh administrator@205.134.224.136:/home/administrator
              //   sshpass -p $STAGE_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.224.136 -p 9376 "sed -i 's/BRANCH_NAME=\\"dev-ci\\"/BRANCH_NAME=\\"stage-ci\\"/g' deploy_service.sh"
              //   sshpass -p $STAGE_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.224.136 -p 9376 "sed -i 's/ENV_NAME=\\"dev\\"/ENV_NAME=\\"stage\\"/g' deploy_service.sh"
              //   sshpass -p $STAGE_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.224.136 -p 9376 chmod +x deploy_service.sh
              //   sshpass -p $STAGE_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.224.136 -p 9376 ./deploy_service.sh ${env.image_tag}
              // """
            }
          }
        }
        stage('Deploy on EKS'){
          when{anyOf{
            expression {env.BRANCH =~ /^refs\/heads\/stage-ci$/}
            expression {env.BRANCH =~ /^origin\/stage-ci$/}
          }}
          stages {
            stage('Checkout helm repo') {
              steps {
                checkout(
                  [
                    $class           : 'GitSCM',
                    branches         : [[name: 'main']],
                    extensions       : [[$class: 'RelativeTargetDirectory',
                    relativeTargetDir: 'helm']],
                    userRemoteConfigs: [[url: 'git@github.com:Drawer-Inc/helm.git', credentialsId: "${gitCredentialsId}"]],
                  ]
                )
              }
            }
            stage ('Update version') {
              steps{script { sh build_update_version }}
            }
            stage('Push version') {
              steps {
                  sshagent (credentials: ["${gitCredentialsId}"]) {
                  sh '''
                    cd ${WORKSPACE}/helm
                    git config user.email "jenkins@drawer.ai"
                    git config user.name "Jenkins CI"
                    git checkout main
                    git add drawerai-services/drawerai-dev-values.yaml
                    git commit -am "Job updated version."
                    git push origin main
                  '''
                }
              }
            }
          }
        }
      }
    }

    stage('Deploy prod'){
      when {
        anyOf {
          expression {env.BRANCH =~ /^refs\/heads\/main$/}
          expression {env.BRANCH =~ /^refs\/tags\/prod-.+$/}
          expression {env.BRANCH =~ /^origin\/main$/}
        }
      }
      steps {
        slackSend(
          color: 'warning',
          channel: SLACK_CHANNEL,
          message: "*${env.JOB_NAME}* - <${env.RUN_DISPLAY_URL}|#${env.BUILD_NUMBER}> " +
            "\n:warning: *WARNING* :warning: it seems to be deploying on PROD environment! " +
            "\nPlease, approve this step in Jenkins via <${env.JOB_URL}|link> " +
            "\n*Additional info:*" +
            "\nRepository: *${gitRepoUrl}*" +
            "\nCommit Hash: *${env.GIT_COMMIT}*",
          teamDomain: SLACK_DOMAIN,
          token: SLACK_TOKEN
        )
        timeout(time: 10, unit: "MINUTES") {
          input message: 'Do you want to approve this deployment on prod?', ok: 'Approve'
        }
        slackSend(
          color: 'good',
          channel: SLACK_CHANNEL,
          message: "Job *${env.JOB_NAME}* (<${env.RUN_DISPLAY_URL}|#${env.BUILD_NUMBER}>) is *approved* to deploy on PROD" +
          "\n:thumbsup:",
          teamDomain: SLACK_DOMAIN,
          token: SLACK_TOKEN
        )
        script {${env.image_tag}
              sh """
                sshpass -p $PROD_PASSWORD scp -o StrictHostKeyChecking=no -P 9376 deploy_service.sh administrator@205.134.233.2:/home/administrator/prod/jenkins/pdf_elements_parsing_service
                sshpass -p $PROD_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.233.2 -p 9376 "sed -i 's/BRANCH_NAME=\\"dev-ci\\"/BRANCH_NAME=\\"main\\"/g' /home/administrator/prod/jenkins/pdf_elements_parsing_service/deploy_service.sh"
                sshpass -p $PROD_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.233.2 -p 9376 "sed -i 's/ENV_NAME=\\"dev\\"/ENV_NAME=\\"prod\\"/g' /home/administrator/prod/jenkins/pdf_elements_parsing_service/deploy_service.sh"
                sshpass -p $PROD_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.233.2 -p 9376 chmod +x /home/administrator/prod/jenkins/pdf_elements_parsing_service/deploy_service.sh 
                sshpass -p $PROD_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.233.2 -p 9376 "cd prod/jenkins/pdf_elements_parsing_service && ./deploy_service.sh ${env.image_tag}"
              """
        }
      }
    }

    stage('Rollback prod'){
      when {
        anyOf {
          expression {env.BRANCH =~ /^origin\/rollback$/}
          expression {env.BRANCH =~ /^refs\/heads\/rollback$/}
        }
      } 
      steps {
        slackSend(
          color: 'warning',
          channel: SLACK_CHANNEL,
          message: "*${env.JOB_NAME}* - <${env.RUN_DISPLAY_URL}|#${env.BUILD_NUMBER}> " +
            "\n:warning: *WARNING* :warning: you activated rollback! " +
            "\nPlease, choose proper rollback version and approve this step in Jenkins via <${env.JOB_URL}|link> " +
            "\n*Additional info:*" +
            "\nRepository: *${gitRepoUrl}*" +
            "\nCommit Hash: *${env.GIT_COMMIT}*",
          teamDomain: SLACK_DOMAIN,
          token: SLACK_TOKEN
        )
        script {
            // def SSH_COMMAND = 'sshpass -p ' + STAGE_PASSWORD + ' ssh -o StrictHostKeyChecking=no administrator@205.134.224.136 -p 9376'
            // def DOCKER_IMAGES_COMMAND = 'docker images 064427434392.dkr.ecr.us-east-1.amazonaws.com/' + SERVICE_NAME + ' --format "{{json . }}"'
            // def PARSE_COMMAND = 'jq -r "select(.Tag != \"<none>\") | \"\(.Created) \(.Tag)\"" | sort -r | awk "{print $2}" | head -2'
            // def tag_output = sh(script: SSH_COMMAND + ' "' + DOCKER_IMAGES_COMMAND + '" | ' + PARSE_COMMAND, returnStdout: true).trim()
            def dockerParsedTags = sh(script: """
              sshpass -p $STAGE_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.224.136 -p 9376 "docker images '064427434392.dkr.ecr.us-east-1.amazonaws.com/pdf_elements_parsing_service' --format '{{json . }}'" 
            """, returnStdout: true).trim()
        
            env.PARSED_TAGS = sh(script: """echo '${dockerParsedTags}' | jq -r '.Tag' | grep -v '<none>'""", returnStdout: true).trim()

            echo "Docker Tags: ${PARSED_TAGS}"  
        }
        timeout(time: 5, unit: "MINUTES") {
          script {
              env.ROLLBACK_VERSION = input(
                id: 'userInput', 
                message: "Please enter the tag\nProposed tags is:\n${PARSED_TAGS}", 
                ok: 'Submit',
                parameters: [string(defaultValue: '', description: '', name: 'tagToReplace')]
            )
          }
        }
        slackSend(
          color: 'good',
          channel: SLACK_CHANNEL,
          message: "Rollback *${env.JOB_NAME}* (<${env.RUN_DISPLAY_URL}|#${env.BUILD_NUMBER}>) is *approved* with ${ROLLBACK_VERSION} version" +
          "\n:thumbsup:",
          teamDomain: SLACK_DOMAIN,
          token: SLACK_TOKEN
        )
        script {
          def SCP_COMMAND = "sshpass -p $STAGE_PASSWORD scp -o StrictHostKeyChecking=no -P 9376"
          def SSH_COMMAND = "sshpass -p $STAGE_PASSWORD ssh -o StrictHostKeyChecking=no administrator@205.134.224.136 -p 9376"
          sh """
            $SCP_COMMAND rollback_service.sh administrator@205.134.224.136:/home/administrator
            $SSH_COMMAND chmod +x rollback_service.sh 
            $SSH_COMMAND ./rollback_service.sh ${ROLLBACK_VERSION}
          """
        }
      }
      
    }

  }

  post {
    always {
      junit allowEmptyResults: true, testResults: '**/*Test.xml'
      cleanWs()
    }

    aborted {
      wrap([$class: 'BuildUser']) {
        slackSend(
          color: '#808080',
          channel: SLACK_CHANNEL,
          message: "*${env.JOB_NAME}* - <${env.RUN_DISPLAY_URL}|#${env.BUILD_NUMBER}> " +
            "Aborted after ${currentBuild.durationString.replaceAll(' and counting', '')}" +
            "\nRepository: *${gitRepoUrl}*" +
            "\nBranch: *${BRANCH}*" +
            "\nCommit Hash: *${env.GIT_COMMIT}*" +
            // "\nLaunched by: *${env.BUILD_USER}*" +
            "\n:octagonal_sign:",
          teamDomain: SLACK_DOMAIN,
          token: SLACK_TOKEN
        )
      }
    }

    failure {
      wrap([$class: 'BuildUser']) {
        slackSend(
          color: 'danger',
          channel: SLACK_CHANNEL,
          message: "*${env.JOB_NAME}* - <${env.RUN_DISPLAY_URL}|#${env.BUILD_NUMBER}> " +
            "Failed after ${currentBuild.durationString.replaceAll(' and counting', '')}" +
            "\nRepository: *${gitRepoUrl}*" +
            "\nBranch: *${env.GIT_BRANCH}*" +
            "\nCommit Hash: *${env.GIT_COMMIT}*" +
            // "\nLaunched by: *${env.BUILD_USER}*" +
            "\n:poop:",
          teamDomain: SLACK_DOMAIN,
          token: SLACK_TOKEN
        )
      }
    }

    success {
      wrap([$class: 'BuildUser']) {
        slackSend(
          color: 'good',
          channel: SLACK_CHANNEL,
          message: "*${env.JOB_NAME}* - <${env.RUN_DISPLAY_URL}|#${env.BUILD_NUMBER}> " +
            "Success after ${currentBuild.durationString.replaceAll(' and counting', '')}" +
            "\nRepository: *${gitRepoUrl}*" +
            "\nBranch: *${env.GIT_BRANCH}*" +
            "\nCommit Hash: *${env.GIT_COMMIT}*" +
            // "\nLaunched by: *${env.BUILD_USER}*" +
            "\n:tada:",
          teamDomain: SLACK_DOMAIN,
          token: SLACK_TOKEN
        )
      }
    }
  }

}