import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Input } from "@/design-system/ui/input";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Badge } from "@/design-system/ui/badge";
import { Separator } from "@/design-system/ui/separator";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/design-system/ui/accordion";
import TopNavigation from "@features/shared/components/top-navigation";
import ChatInterface from "@features/shared/components/chat-interface";

export default function HelpSupport() {
  const [searchQuery, setSearchQuery] = useState("");

  const user = {
    id: "user-1",
    name: "Avery Chen",
    avatar: "https://avatar.vercel.sh/avery",
  };

  const ai = {
    id: "ai-1",
    name: "Orcheo Canvas Support",
    avatar: "https://avatar.vercel.sh/orcheo-canvas",
    isAI: true,
  };

  const initialMessages = [
    {
      id: "msg-1",
      content:
        "Hello! I'm the Orcheo Canvas support assistant. How can I help you today?",
      sender: ai,
      timestamp: new Date(Date.now() - 60000),
    },
  ];

  return (
    <div className="flex min-h-screen flex-col">
      <TopNavigation />

      <div className="flex-1 space-y-4 p-8 pt-6 mx-auto w-full max-w-7xl">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Help & Support</h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card className="col-span-full">
            <CardHeader>
              <CardTitle>How can we help you?</CardTitle>
              <CardDescription>
                Search our knowledge base or contact support
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="relative">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground"
                >
                  <circle cx="11" cy="11" r="8" />

                  <path d="m21 21-4.35-4.35" />
                </svg>
                <Input
                  type="search"
                  placeholder="Search for help articles..."
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Documentation</CardTitle>
              <CardDescription>Explore our guides and examples</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
                </svg>
                Getting Started Guide
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
                </svg>
                API Reference
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
                </svg>
                Workflow Examples
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
                </svg>
                Node Reference
              </Link>
            </CardContent>
            <CardFooter>
              <Button variant="outline" className="w-full">
                View All Documentation
              </Button>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Video Tutorials</CardTitle>
              <CardDescription>
                Learn through step-by-step videos
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Introduction to Orcheo Canvas
                <Badge variant="secondary" className="ml-auto">
                  New
                </Badge>
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Building Your First Workflow
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Advanced Workflow Techniques
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Debugging and Troubleshooting
              </Link>
            </CardContent>
            <CardFooter>
              <Button variant="outline" className="w-full">
                View All Tutorials
              </Button>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Community</CardTitle>
              <CardDescription>
                Connect with other Orcheo Canvas users
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M17 14v6m-3-3h6M9.5 8.5h5M8 14a6 6 0 1 1 0-12 6 6 0 0 1 0 12Z" />
                </svg>
                Community Forum
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M15 11h.01M11 15h.01M16 16h.01M11 11h.01M7 11h.01M16 11h.01M15 15h.01M7 15h.01M11 11h.01" />

                  <rect width="18" height="18" x="3" y="3" rx="2" />
                </svg>
                Discord Server
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />

                  <rect width="4" height="12" x="2" y="9" />

                  <circle cx="4" cy="4" r="2" />
                </svg>
                LinkedIn Group
              </Link>
              <Link
                to="#"
                className="flex items-center gap-2 rounded-md p-2 hover:bg-muted"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z" />
                </svg>
                Twitter
              </Link>
            </CardContent>
            <CardFooter>
              <Button variant="outline" className="w-full">
                Join Our Community
              </Button>
            </CardFooter>
          </Card>
        </div>

        <Tabs defaultValue="faq" className="space-y-4">
          <TabsList>
            <TabsTrigger value="faq">Frequently Asked Questions</TabsTrigger>
            <TabsTrigger value="contact">Contact Support</TabsTrigger>
          </TabsList>
          <TabsContent value="faq" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Frequently Asked Questions</CardTitle>
                <CardDescription>
                  Find answers to common questions about Orcheo Canvas
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Accordion type="single" collapsible className="w-full">
                  <AccordionItem value="item-1">
                    <AccordionTrigger>
                      What is Orcheo Canvas and how does it work?
                    </AccordionTrigger>
                    <AccordionContent>
                      Orcheo Canvas is a visual workflow automation platform
                      that allows you to create, manage, and run automated
                      workflows without coding. It works by connecting various
                      nodes (actions, triggers, and logic) in a visual canvas to
                      create powerful automation flows.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-2">
                    <AccordionTrigger>
                      How do I create my first workflow?
                    </AccordionTrigger>
                    <AccordionContent>
                      To create your first workflow, click the "New Workflow"
                      button on the dashboard. You'll be taken to the workflow
                      editor where you can add a trigger node to start your
                      workflow, then add action nodes to perform tasks, and
                      connect them together. Save your workflow when you're
                      done, and you can activate it to start running.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-3">
                    <AccordionTrigger>
                      What types of integrations are available?
                    </AccordionTrigger>
                    <AccordionContent>
                      Orcheo Canvas supports a wide range of integrations
                      including popular services like Google Workspace,
                      Microsoft 365, Slack, Salesforce, HubSpot, and many more.
                      We also support HTTP requests, webhooks, and database
                      connections, allowing you to connect to virtually any
                      service with an API.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-4">
                    <AccordionTrigger>
                      How do I debug a workflow that's not working?
                    </AccordionTrigger>
                    <AccordionContent>
                      Orcheo Canvas provides several debugging tools. You can
                      use the execution history to see past runs and their
                      results. The workflow debugger allows you to step through
                      your workflow node by node, inspecting the data at each
                      step. You can also add breakpoints to pause execution at
                      specific points and examine the state of your workflow.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-5">
                    <AccordionTrigger>
                      How do I manage team access and permissions?
                    </AccordionTrigger>
                    <AccordionContent>
                      In the Settings page under the Teams tab, you can invite
                      team members and assign them different roles (Owner,
                      Admin, Editor, or Viewer). Each role has different
                      permissions, allowing you to control who can view, edit,
                      or manage workflows and other resources in your account.
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </CardContent>
              <CardFooter>
                <Button variant="outline" className="w-full">
                  View All FAQs
                </Button>
              </CardFooter>
            </Card>
          </TabsContent>
          <TabsContent value="contact" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Contact Support</CardTitle>
                <CardDescription>
                  Get help from our support team
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <label
                        htmlFor="name"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        Name
                      </label>
                      <Input id="name" placeholder="Enter your name" />
                    </div>
                    <div className="grid gap-2">
                      <label
                        htmlFor="email"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        Email
                      </label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="Enter your email"
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <label
                      htmlFor="subject"
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                      Subject
                    </label>
                    <Input id="subject" placeholder="Enter subject" />
                  </div>
                  <div className="grid gap-2">
                    <label
                      htmlFor="message"
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                      Message
                    </label>
                    <textarea
                      id="message"
                      className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      placeholder="Enter your message"
                    />
                  </div>
                </div>
              </CardContent>
              <CardFooter className="flex justify-between">
                <Button variant="outline">Cancel</Button>
                <Button>Submit</Button>
              </CardFooter>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
          <div className="p-6 flex flex-col md:flex-row items-center gap-4">
            <div className="flex-1">
              <h3 className="text-2xl font-bold">Need immediate help?</h3>
              <p className="text-muted-foreground">
                Chat with our AI assistant for instant answers
              </p>
            </div>
            <ChatInterface
              title="Orcheo Canvas Support"
              initialMessages={initialMessages}
              user={user}
              ai={ai}
              triggerButton={
                <Button size="lg" className="w-full md:w-auto">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="mr-2 h-4 w-4"
                  >
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                  Chat with Support
                </Button>
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}
